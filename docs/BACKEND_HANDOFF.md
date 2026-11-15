# Backend handoff — Maulik and Dhaush

Written 14 Nov 2026 for sunhacks. Read `CLAUDE.md` and `docs/SPEC.md` first (10 minutes). This file tells you exactly what the two of you build, how the pieces talk to each other, and what Shrey's dashboard expects from you.

**Ownership**

| Who | Owns | Files |
| --- | --- | --- |
| **Shrey** | The dashboard UI (what judges look at) | `static/dashboard.html`, `static/*.css`, `static/*.js` |
| **Maulik** | Phone + voice: Twilio call in, audio conversion, Gemini Live conversation, voice tools | `app/twilio_stream.py`, `app/audio.py`, `app/voice_brain.py` |
| **Dhaush** | Browser agent: Playwright browser, computer-use loop, safety guard | `app/task_runner.py`, `app/safety.py`, `scripts/try_task.py`, `tests/` |
| **Both** | The glue: FastAPI app, the shared event bus, the dashboard WebSocket, call logs | `app/main.py`, `app/events.py`, `app/dashboard.py`, `app/call_log.py` |

If you'd rather swap the Maulik/Dhaush split, fine, just tell the group so Shrey knows who to ask about what.

Use Claude Code for the actual code. `docs/BUILD_STEPS.md` has a paste-ready prompt per milestone. This file adds the contracts and details those prompts leave out.

---

## 1. The one rule that makes parallel work possible

**Every module talks to the others only through `app/events.py`.** Nobody imports the dashboard from the task runner, or the task runner from the Twilio code. You publish an event; whoever cares subscribes.

```python
# app/events.py  (build this FIRST, together, in the first 30 minutes)
import asyncio, time
from typing import Any, Awaitable, Callable

Listener = Callable[[dict], Awaitable[None]]

class EventBus:
    def __init__(self) -> None:
        self._listeners: list[Listener] = []
        self.history: list[dict] = []          # replayed to a dashboard that connects late

    def subscribe(self, fn: Listener) -> None: ...
    async def publish(self, type: str, **data: Any) -> None:
        event = {"type": type, "ts": time.time(), **data}
        self.history.append(event)
        print(f"[event] {event}")               # every event also goes to the console
        for fn in list(self._listeners):
            asyncio.create_task(fn(event))

bus = EventBus()                                # one shared instance, import this everywhere
```

That's the whole backbone. The dashboard WebSocket forwards every event to the browser; the voice brain listens for task events and speaks them; the call log writes them to a file.

---

## 2. The contract with Shrey's dashboard (do not change without telling him)

### HTTP

| Method + path | Returns | Notes |
| --- | --- | --- |
| `GET /` | tiny "TechTwin is running" page | Milestone 0 |
| `GET /dashboard` | `static/dashboard.html` | Shrey's file, you just serve it |
| `GET /api/state` | JSON snapshot: `{"call": ..., "task": ..., "steps": [...], "transcript": [...], "pending_approval": ... \| null, "blocked": ... \| null}` | So a reloaded dashboard isn't blank |
| `GET /api/screenshot` | latest browser screenshot as `image/jpeg` | ~70% quality, 1280 px wide max. Dashboard polls or reloads on `screenshot` events |
| `POST /api/reset` | `{"ok": true}` | Stops any task, closes browser pages, clears state. Demo-proof button (Milestone 8) |
| `POST /api/confirm`, `POST /api/cancel` | `{"ok": true}` | Same as the voice tools, but from the dashboard. Backup if the voice approval is misheard live |
| `POST /api/start_task` body `{"goal": "..."}` | `{"ok": true}` | Lets us demo the browser agent even if the phone line is down |
| `POST /voice` | TwiML | Twilio webhook (Maulik) |
| `WS /media` | — | Twilio Media Streams (Maulik) |
| `WS /ws/dashboard` | — | Shrey's page connects here |

### WebSocket `/ws/dashboard`

On connect: send `{"type": "snapshot", ...same as /api/state}` then stream events live. Every message is one JSON object with a `type` and a `ts` (Unix seconds). These are the types Shrey will render:

| `type` | Fields | Meaning |
| --- | --- | --- |
| `call_started` | `call_sid`, `from` (last 4 digits only) | Phone rang and connected |
| `call_ended` | `call_sid`, `duration_s` | Caller hung up |
| `transcript` | `who`: `"caller"` \| `"techtwin"`, `text`, `final`: bool | Live transcript. `final: false` = still being spoken, replace the last bubble |
| `task_started` | `task_id`, `goal` | start_task was called |
| `step` | `task_id`, `n`, `action` (`click`/`type`/`scroll`/`open_url`/`key`/`wait`), `summary` (plain words, e.g. "Clicked the Search box"), `status`: `"running"` \| `"done"` \| `"failed"` | One row in the step list |
| `screenshot` | `task_id`, `n`, `url` = `/api/screenshot?v=<n>` | New screenshot available |
| `needs_approval` | `task_id`, `step_n`, `question` (e.g. "Shall I press Join?"), `reason` | **Big yellow banner** |
| `approval_result` | `task_id`, `approved`: bool, `by`: `"voice"` \| `"dashboard"` | Banner goes away |
| `blocked` | `task_id`, `reason` (e.g. "This page asks for a password"), `url` | **Big red banner**, task over |
| `task_finished` | `task_id`, `outcome`: `"done"` \| `"cancelled"` \| `"blocked"` \| `"timeout"` \| `"failed"`, `summary`, `duration_s`, `steps` | Task over |
| `agent_speaking` | `speaking`: bool | So the UI can show a "talking" indicator |
| `error` | `where`, `message` | Anything unexpected. UI shows it small, never crashes |
| `reset` | — | Clear everything |

**Plain words only in `summary`, `question`, `reason`.** No selectors, no URLs longer than the domain, no "DOM" or "XPath". Judges read this screen.

---

## 3. Maulik: phone + voice (Milestones 1, 2, 3, then 7)

### 3.1 Twilio phone line (`app/twilio_stream.py`)

- `POST /voice` returns TwiML: `<Response><Say>Hi, this is TechTwin.</Say><Connect><Stream url="wss://<PUBLIC_BASE_URL host>/media"/></Connect></Response>`. The `<Say>` buys you a second while the WebSocket connects.
- `WS /media` receives JSON frames from Twilio. Event names: `connected`, `start` (gives you `streamSid` and `callSid`, save both), `media` (`payload` = base64 μ-law, 8 kHz, 20 ms = 160 bytes per frame), `stop`.
- To send audio back: `{"event": "media", "streamSid": sid, "media": {"payload": base64_mulaw}}`. Must be 8 kHz μ-law. Send in 20 ms chunks, don't blast a whole 5-second clip at once.
- To cut off playback (barge-in): send `{"event": "clear", "streamSid": sid}`.
- Publish `call_started` on `start`, `call_ended` on `stop`.

Twilio setup: Console → Phone Numbers → your number → Voice → "A call comes in" = Webhook, `https://<ngrok>/voice`, HTTP POST. **A trial account only accepts calls from verified numbers.** Verify every teammate's phone and the demo phone now (Console → Verified Caller IDs), or put ~$20 credit on the account so any judge can call. **ngrok's URL changes every time you restart it** on the free plan; re-paste it into Twilio and `.env` every time, or reserve a free static domain in the ngrok dashboard (recommended, do this once).

### 3.2 Audio conversion (`app/audio.py`)

Pure functions, numpy only, each with a 3-line docstring and a unit test:

```python
def mulaw_to_pcm16(data: bytes) -> np.ndarray      # 8 kHz μ-law bytes → int16 samples
def pcm16_to_mulaw(samples: np.ndarray) -> bytes   # int16 samples → μ-law bytes
def resample(samples: np.ndarray, src_hz: int, dst_hz: int) -> np.ndarray   # 8k↔16k↔24k, linear interp is fine
def twilio_in_to_gemini(payload_b64: str) -> bytes     # base64 μ-law 8k → raw PCM16 16 kHz bytes
def gemini_out_to_twilio(pcm24k: bytes) -> list[str]   # PCM16 24 kHz → list of base64 μ-law 8k 20 ms chunks
```

Gemini Live expects **16 kHz, 16-bit, mono, little-endian PCM** in, and sends **24 kHz PCM** out. Twilio is 8 kHz μ-law both ways. Getting one of these wrong gives you chipmunk or slow-motion audio; the echo test in Milestone 2 catches it before Gemini is involved.

### 3.3 Voice brain (`app/voice_brain.py`)

- Use `google-genai`: `client.aio.live.connect(model=..., config=...)`. One Live session per phone call, opened on `start`, closed on `stop`.
- **Model name:** as of today the Developer API lists `gemini-2.5-flash-native-audio-preview-12-2025` (stable choice) and `gemini-3.1-flash-live-preview` (newest, free tier). Put it in `.env` as `GEMINI_LIVE_MODEL` so we can swap without a code change. Verify on the Live API docs page before you start, names move.
- Config: `response_modalities=["AUDIO"]`, system instruction = the "Voice and tone" + "Safety rules" sections of `CLAUDE.md` plus the greeting from `SPEC.md` step 2, input and output audio transcription turned on (that's where the `transcript` events come from), and the tool declarations below.
- Two concurrent loops per call: Twilio→Gemini (convert, `session.send_realtime_input(audio=...)`) and Gemini→Twilio (convert, chunk, send). Barge-in: Gemini sends an `interrupted` signal when the caller talks over it; on that, send Twilio `clear` and drop your outbound queue.
- Publish `transcript` (both sides), `agent_speaking`.

### 3.4 Voice tools (Milestone 7, with Dhaush)

Declare these as Gemini function tools. When Gemini calls one, run it and send the function response back.

| Tool | What it does |
| --- | --- |
| `start_task(goal: str)` | `task_runner.start(goal)`; return "Started" immediately, don't block |
| `confirm_action()` | `task_runner.confirm()` |
| `cancel_action()` | `task_runner.cancel()` |
| `describe_screen()` | returns `task_runner.describe()`: one or two plain sentences about the current screenshot |
| `stop_task()` | `task_runner.stop()` |

The voice brain also **subscribes to the bus**: on `step` with `status: done` push a short text turn into the session so Gemini narrates it ("I've opened YouTube"), but throttle to at most one narration every ~4 seconds, summarise, skip scrolls. On `needs_approval` push the `question` and let Gemini ask it. On `blocked` push the reason. On `task_finished` push the summary. **Stop word:** if a caller transcript contains "stop", "cancel" or "no no no", call `task_runner.stop()` directly in code, don't wait for the model to decide.

---

## 4. Dhaush: browser agent + safety (Milestones 4, 5, then 7, 8)

### 4.1 Task runner (`app/task_runner.py`)

One module-level `TaskRunner` with an asyncio-friendly API:

```python
class TaskRunner:
    async def start(self, goal: str) -> str          # returns task_id; refuses if a task is already running
    async def confirm(self) -> None                  # resolves a pending approval
    async def cancel(self) -> None                   # cancels the pending step, task continues or ends
    async def stop(self) -> None                     # hard stop, within 1 second
    async def describe(self) -> str                  # plain-words description of current screen
    async def reset(self) -> None                    # stop + fresh page at start URL
    def snapshot(self) -> dict                       # for /api/state
```

The loop, per step:
1. Screenshot (Playwright `page.screenshot`, JPEG, store latest in memory for `/api/screenshot`, publish `screenshot`).
2. Ask the computer-use model: screenshot + goal + history → next action.
3. `safety.check(action, page)` → `allow` / `ask_first(reason)` / `block(reason)`.
4. On `ask_first`: publish `needs_approval`, `await` an `asyncio.Event` that `confirm()` sets (or `cancel()` clears). Timeout 60 s → treat as cancel.
5. Execute via Playwright. Publish `step` running → done/failed.
6. Stop when the model says done, after `MAX_TASK_STEPS` (25), or after `MAX_TASK_SECONDS` (120, wrap the whole loop in `asyncio.wait_for`). Publish `task_finished`.

Playwright: `chromium.launch(headless=False)`, one persistent `BrowserContext` for the whole server lifetime, viewport 1280×800 so screenshots are small and the model's coordinates are easy. Launch it once at app startup, not per task. In `DEMO_MODE` open `about:blank` or a simple local start page on reset.

**Computer-use model:** the dedicated preview is `gemini-2.5-computer-use-preview-10-2025` (most guides use it). Google's docs now recommend the newer Gemini 3.x Flash models for computer use and their official `google-gemini/computer-use-preview` repo on GitHub is a Playwright-based reference loop worth reading before you write yours (study it, don't paste it; hackathon rule). Put the name in `.env` as `COMPUTER_USE_MODEL`. The Gemini computer-use tool returns actions like `click_at`, `type_text_at`, `scroll_document`, `navigate`, `key_combination`, `wait_5_seconds` with coordinates on a 0–999 grid that you scale to the viewport. Fallback if Gemini quota or the model misbehaves: Claude computer use via `anthropic` (`ANTHROPIC_API_KEY` is already in `.env.example`); keep the provider behind one `propose_action(screenshot, goal, history) -> Action` function so swapping is a one-line change.

`scripts/try_task.py "goal"`: runs one task from the terminal with no phone and no dashboard, prints every event, prompts `y/n` in the terminal for `ask_first`. This is your main dev loop and also our fallback demo.

### 4.2 Safety guard (`app/safety.py`)

```python
@dataclass
class Verdict:
    kind: Literal["allow", "ask_first", "block"]
    reason: str = ""

async def check(action: Action, page: Page) -> Verdict
```

Rules, in this order (first match wins):
1. **Block** if the action's target URL, or the current page URL after navigation, has a host not in `ALLOWED_DOMAINS` (match the registered domain, so `www.youtube.com` passes for `youtube.com`).
2. **Block** if the page has `input[type=password]`, any `autocomplete^="cc-"` field, or visible text matching card number / CVV / expiry, or the URL path contains `checkout`, `payment`, `billing`, `pay`.
3. **Ask first** if the element under the click (use `page.evaluate` with `document.elementFromPoint(x, y)`, read its text, `aria-label`, `value`, `title`) matches, case-insensitive: join, send, submit, buy, pay, order, delete, remove, download, install, allow, accept, sign up, confirm, purchase, add to bag, add to cart, continue to checkout. Also ask first before the `Enter` key on a form.
4. **Allow** everything else.

The `reason` is spoken to the caller and shown on the red/yellow banner, so write it like "This page asks for a password" not "password input detected". `tests/test_safety.py` with a fake page object for each rule; run with `pytest`. Milestone 5's check: "Buy an iPhone on apple.com" must end in `blocked`, "join the Zoom meeting" must `needs_approval` before Join.

### 4.3 Describe screen

`describe()` sends the latest screenshot to a normal Gemini text model (`gemini-2.5-flash` or newer) with "Describe this screen to a 75-year-old in two short sentences. No technical words." Cache the result per screenshot so repeated asks are instant.

---

## 5. Both: the glue

- `app/main.py`: FastAPI app, `load_dotenv()`, mounts `static/`, includes the routers, starts Playwright on startup, closes on shutdown.
- `app/dashboard.py`: `/ws/dashboard` handler. On connect send snapshot, then subscribe to the bus and forward. Keep a set of live sockets, drop dead ones silently. `/api/state`, `/api/screenshot`, `/api/reset`, `/api/confirm`, `/api/cancel`, `/api/start_task`.
- `app/call_log.py`: subscribe to the bus, append one JSON line per event to `logs/<date>/<call_sid or task_id>.jsonl`. This is where the "measured proof" numbers for the pitch come from (task duration, steps, approvals, blocks). Write a tiny `scripts/stats.py` that prints average task time and count of unsafe actions (which must be 0).
- `requirements.txt`: `fastapi`, `uvicorn[standard]`, `websockets`, `twilio`, `google-genai`, `anthropic`, `playwright`, `python-dotenv`, `numpy`, `pytest`, `pytest-asyncio`. Then `playwright install chromium`.

---

## 6. Setup checklist (first hour)

1. Clone: `git clone https://github.com/shrey-Bish/Tech-Twin.git`, open in VS Code with the Claude Code extension.
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && playwright install chromium`
3. `cp .env.example .env` and fill it in. Add these new keys to **both** files: `GEMINI_LIVE_MODEL`, `COMPUTER_USE_MODEL`.
4. Accounts: Twilio (number + verified callers), Gemini key from aistudio.google.com, ngrok (reserve the static domain), optionally an Anthropic key.
5. `uvicorn app.main:app --reload --port 8000` in one terminal, `ngrok http 8000` in another.
6. Build `app/events.py` together, then split.

---

## 7. Order of work and sync points

| When | Maulik | Dhaush | Sync |
| --- | --- | --- | --- |
| Hour 0–1 | Setup, events.py together | Setup, events.py together | Agree on event names above |
| Hour 1–4 | M1 phone answers, M2 echo | M4 agent runs a YouTube task from the terminal | Shrey has the WS contract and builds UI against fake events (`scripts/fake_events.py`: replays a scripted event sequence onto the bus every 2 s — **Dhaush writes this first**, it unblocks Shrey) |
| Hour 4–8 | M3 real conversation with Gemini | M5 safety guard + tests | Dashboard shows real steps from try_task.py |
| Hour 8–12 | M7 tools + narration | M7 approvals over voice, stop word | **Full end-to-end call.** Everyone present |
| After | M8 demo-proofing: timeouts, recovery phrases, reset, call logs | Same | Run each demo task 5×, record the numbers |

---

## 8. Known traps

- **Twilio frames are 20 ms.** Send outbound audio paced in 20 ms chunks or you get stutter and Twilio drops frames.
- **`streamSid` is required on every outbound frame.** Grab it from the `start` event.
- **Gemini Live sessions have a time limit** (around 10–15 minutes of audio). Fine for a demo; don't hold a session open between calls.
- **ngrok free URL rotates** on every restart. Static domain, see above.
- **Playwright on macOS** will steal focus when it opens Chromium. For the demo that's what we want (the browser comes forward). For dev, launch it on a second display.
- **Never two tasks at once.** `start()` must refuse while one is running and say so in plain words.
- **Coordinates:** the computer-use model gives normalised 0–999 coordinates. Scale to the viewport before clicking. Off-by-one here looks like "the agent is drunk".
- **Secrets:** `.env` is gitignored. If a key ever lands in a commit, rotate it, don't just delete the line.
- **Hackathon rule:** all code written during the event. Reading Google's sample repo is fine; copying files in is not.

---

## 9. What "done" means for the backend

- `python scripts/try_task.py "Go to YouTube and play a Ranveer Brar dal recipe video"` completes 4 of 5 runs, asks before Play.
- `python scripts/try_task.py "Buy an iPhone on apple.com"` ends in `blocked` every time.
- A phone call: greeting, task by voice, approval by voice, "stop" halts within a second.
- Every one of those shows live on Shrey's dashboard with no `error` events.
- `pytest` green. `logs/` has one file per call with the numbers for the pitch.

Questions: ask in the group chat, tag the owner from the table at the top. Change this file when you change a contract.

## Implementation note: Maulik's voice interface

The initial phone/voice backend now uses the shared event bus for all browser
commands, as required by section 1. See [Maulik's setup guide](MAULIK_SETUP.md)
for the `voice_command` / `voice_command_result` fields and runner-listener
example. `app/main.py` and `app/events.py` are in place; merge these shared files
carefully when adding browser startup and the remaining dashboard endpoints.

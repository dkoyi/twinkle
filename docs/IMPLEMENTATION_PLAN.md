# TechTwin — implementation plan (v2)

Written 14 Nov 2026, after reading the sunhacks opening slides and the sponsor/MLH prize pages. This sits on top of `CLAUDE.md`, `docs/SPEC.md` and `docs/BACKEND_HANDOFF.md`. Where they disagree, **this file wins on scope and priority**; the handoff still wins on event names and API shapes.

## 1. Scope decision

We compete for **Best Overall** and enter exactly two sponsor prizes:

| Prize | Role | Priority |
| --- | --- | --- |
| **Best Overall** | The real goal. Reliable live demo, polished UI, the safety story | Everything |
| **Best Use of Gemini API** (MLH) | Gemini is the backbone: voice, computer use, screen description | **Build first, finish first** |
| **Supermemory** (we have credits) | Remembers Grandma's family, sites and past tasks | **Last.** Only after the Gemini path works end to end |

**Dropped:** Tiger Data, Solana, TinyFish, Vultr, Auth0, AWS, MongoDB. Call logs stay as local JSONL files. Public URL stays ngrok.

**Hard rules from the slides:** hacking is 11:10 AM Sat to **11:00 AM Sun, late submissions not accepted**. Devpost must be filled in. Demo is 3 minutes plus 2 minutes of questions, and **the hack is judged, not slides**. No commits before hacking starts or after it ends. Submit early.

## 2. Who builds what

| Area | Owner | Files |
| --- | --- | --- |
| Dashboard UI + family page | Shrey (with Claude Code here) | `static/*`, `scripts/fake_events.py` |
| Phone + Gemini Live voice | Maulik | `app/twilio_stream.py`, `app/audio.py`, `app/voice_brain.py` |
| Browser agent + safety | Dhaush | `app/task_runner.py`, `app/safety.py`, `scripts/try_task.py`, `tests/` |
| Glue | Maulik + Dhaush | `app/main.py`, `app/events.py`, `app/dashboard.py`, `app/call_log.py` |
| Memory (Supermemory) | Whoever is free, **last** | `app/memory.py` |

The UI work does **not** touch `app/*`. It only needs the event contract in `docs/BACKEND_HANDOFF.md` section 2, so it can run against fake events with no backend.

## 2b. Foundation that already exists (pull before you start)

| File | What it gives you |
| --- | --- |
| `app/events.py` | The shared `bus`. `await bus.publish("step", ...)` from anywhere; `bus.state` keeps the live snapshot |
| `app/dashboard.py` | `/ws/dashboard`, `/api/state`, `/api/screenshot`, and the button endpoints. Call `set_screenshot(jpeg_bytes)` to get the URL for a `screenshot` event |
| `app/main.py` | The FastAPI app. Add your routers here and launch Playwright in `lifespan` |
| `app/dev_replay.py` | `POST /api/dev/replay?scenario=dal` or `iphone` plays an explicitly simulated call; opt-in with `DEV_REPLAY=true` (localhost only) |
| `static/*` | The dashboard (`/dashboard`). Practice mode with no server: `/static/dashboard.html?demo=dal` |

**Plugging in:** when your task runner is ready, replace the button defaults, for example `dashboard.hooks.confirm = task_runner.confirm` (same for `cancel`, `stop`, `reset`, `start_task`). Prefer `from app.integration import attach_runner; attach_runner(runner)` so the same runner receives both voice and dashboard commands. Unset hooks no longer publish fake successes. Run with `uvicorn app.main:app --reload --port 8000`, open `http://localhost:8000/talk` for the free browser voice demo and `http://localhost:8000/dashboard` to watch it. The real browser agent and safety guard are now initialized and attached at server startup. The accepted demo uses the browser phone interface; real telephone streaming remains unverified. `pytest` runs the tests.

## 2c. Browser agent (built; needs one real-key test)

Milestones 4, 5 and the browser half of 7 and 8 are in. All `pytest` tests pass (77), including real headless Chromium tests.

| File | What it does |
| --- | --- |
| `app/actions.py` | One action vocabulary. `parse_function_call` maps Gemini 2.5 names (`click_at`, `type_text_at`...) and the newer docs' names (`click`, `type`...) to the same `Action` |
| `app/safety.py` | `check(action, page)` returns allow / ask_first / block, in the handoff's rule order, with plain-words reasons. `check_page(page)` runs after every action |
| `app/browser.py` | The visible Chromium: real mouse glide and click, typing, scrolling, new tabs followed, reset |
| `app/computer_use.py` | The model adapter (`GeminiProvider`) and a `ScriptedProvider` for tests. The only file that knows how Gemini talks |
| `app/task_runner.py` | `runner` (module-level): the loop, approvals, stop, timeout, recovery. Publishes everything on the event bus |
| `app/call_log.py`, `scripts/stats.py` | Logs per call/task and the pitch numbers |
| `scripts/try_task.py` | Run one task from the terminal. `--demo` needs no API key |

**For Maulik (voice tools):** import `from app.task_runner import runner, TaskBusy` and map the tools directly:

```python
start_task(goal)     -> await runner.start(goal)               # raises TaskBusy with a sentence you can speak
confirm_action()     -> await runner.confirm(by="voice")
cancel_action()      -> await runner.cancel(by="voice")
describe_screen()    -> await runner.describe()
stop_task()          -> await runner.stop()                    # also call this yourself on the stop word
```

Subscribe to the bus (`bus.subscribe`) and speak `step` (status done), `needs_approval` (use `question`), `blocked` (use `reason`) and `task_finished` (use `summary`). Every one of those strings is already plain words. A `task_finished` with outcome `failed` or `timeout` is the cue for the "That didn't work, let me try another way" recovery line.

**Step events now carry** an optional `point: {x, y}` (0 to 1 across the screenshot) on clicks and typing, and `screenshot` events carry `page_url`. The dashboard uses them for the click ripple and the address pill.

**Not verified yet (needs a real `GEMINI_API_KEY`):** the exact Gemini request. Google's docs now describe a newer "Interactions API" with different model and action names. We built on `generate_content` with the typed `computer_use` tool, which matches the installed SDK. If a real call errors, only `GeminiProvider` in `app/computer_use.py` needs to change; everything else is model-independent. Run `python scripts/try_task.py "Go to YouTube and play a Ranveer Brar dal recipe video"` to find out. Set `COMPUTER_USE_MODEL` in `.env` to a model your key can use.

**Still to do on the browser side:** a Claude computer-use fallback behind `make_provider()`, tuning step speed for the 90-second demo goal, and running each demo task five times for the numbers.

## 3. Build order

**Phase 1: Gemini backbone (must work before anything else)**
1. `app/events.py` event bus (30 minutes, together).
2. Phone answers (M1), echo test (M2), Gemini Live conversation with barge-in (M3).
3. Browser agent from the terminal (M4) and safety guard with tests (M5).
4. Voice tools wired to the task runner, approvals by voice, stop word (M7).
5. Demo-proofing: reset, timeouts, spoken recovery, call logs (M8).

**Phase 2: UI (parallel with phase 1, against fake events)**
1. Dashboard (below).
2. Family page.
3. Swap fake events for the real bus when M4 lands.

**Phase 3: Supermemory (only after phase 1 passes its checks)**

**Phase 4: proof + submit.** Five testers, backup video, Devpost text. Aim to submit well before 11:00 AM Sunday.

## 4. UI requirements (the most visible part)

Judges read this screen from 2 metres. It must feel fluid, calm and obvious.

**Dashboard (`/dashboard`)**
- Big live screenshot (left), live transcript with large text and a "listening / talking" indicator (right), step list with timestamps and status icons (bottom).
- Yellow **approval banner** with the question in huge text and Yes / No buttons (backup to voice). Red **blocked banner** with a plain reason.
- Smooth transitions: new steps slide in, screenshots cross-fade, banners ease in and out, nothing jumps or flickers. Respect reduced-motion.
- Calm friendly colours, plain words only, never technical terms, no selectors or long URLs.
- Never crashes: unknown event types are ignored, a dropped WebSocket reconnects by itself and replays the snapshot, an empty state looks designed rather than blank.
- Controls: Reset, Start task (for demoing without the phone), Stop.
- Works at 1080p on a projector and on a laptop.

**Family page (`/family`)**: a simple read-only "watch along" view plus Stop and approve buttons, and a list of recent tasks. Same app, same WebSocket. No login.

**Mascot**: a small friendly "twin" character on the dashboard (picks up the sunhacks Best Mascot track for free). Optional, last in the UI queue.

## 5. Backend requirements (what the teammate builds)

Follow `docs/BACKEND_HANDOFF.md` for the full detail. Summary of what must exist:

- **Endpoints:** `GET /dashboard`, `GET /family`, `GET /api/state`, `GET /api/screenshot`, `POST /api/reset|confirm|cancel|start_task`, `POST /voice`, `WS /media`, `WS /ws/dashboard`.
- **Events** (names fixed, see handoff): `call_started`, `call_ended`, `transcript`, `task_started`, `step`, `screenshot`, `needs_approval`, `approval_result`, `blocked`, `task_finished`, `agent_speaking`, `error`, `reset`.
- **Audio:** Twilio 8 kHz mu-law to Gemini 16 kHz PCM in, Gemini 24 kHz PCM to 8 kHz mu-law out, 20 ms paced frames, barge-in via Twilio `clear`.
- **Gemini:** Live model and computer-use model names live in `.env` (`GEMINI_LIVE_MODEL`, `COMPUTER_USE_MODEL`), verified against current docs before coding.
- **Safety:** ask-first words, block on password/card/checkout and non-allowlisted domains, stop word handled in code (not left to the model).
- **Must pass:** the checks in `BACKEND_HANDOFF.md` section 9.

New for this plan: add `GET /family` to the contract, and keep `.env.example` in sync (`GEMINI_LIVE_MODEL`, `COMPUTER_USE_MODEL`, later `SUPERMEMORY_API_KEY`).

## 6. Supermemory (phase 3, last)

Do not start until a full phone call with a voice-approved task works.

- `app/memory.py` wraps the Supermemory SDK behind two functions: `remember(caller_id, text)` and `recall(caller_id, query) -> str`. Check the current Supermemory docs for the API version before writing it (older docs show a different base URL and header).
- Use it for: family member names ("Rahul is my grandson"), favourite sites, and past tasks, so "play the dal video again" works.
- Recall at call start and inject into the Gemini system instruction; store a one-line summary at `task_finished`.
- If Supermemory is down or the key is missing, the app must carry on silently. It can never block a call.
- Show it on the dashboard as a small "TechTwin remembers: ..." chip so judges can see it.

## 7. Demo requirements

Main demo: the YouTube dal video or the Zoom/Meet join, with a spoken approval. Safety demo: "Buy me the new iPhone" ends in a red banner. Backups: `POST /api/start_task` if the phone line fails, and a recorded video. Twilio trial accounts only accept verified numbers, so verify every phone that will call.

## 8. Risks to watch

1. Gemini model names change; read the docs first and keep names in `.env`.
2. Audio sample-rate mistakes (chipmunk or slow voice); the echo test catches this.
3. ngrok URL changes on restart; reserve a static domain.
4. Computer-use coordinates are 0-999 and must be scaled to the viewport.
5. Wi-Fi at the venue; keep the backup video ready.
6. Late submission is not accepted; stop adding features by about 8 AM Sunday.

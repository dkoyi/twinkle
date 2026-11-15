# Maulik: phone and voice

Implemented locally: the phone webhook, authenticated audio stream, echo mode,
Gemini Live conversation, interruptions, live transcripts, and five voice tools.
The real phone/Gemini checks still need your accounts. Browser actions need
Dhaush's event listener described below. No browser actions are simulated as successes.

## Free browser demo (recommended for the hackathon)

The browser demo needs only GEMINI_API_KEY in .env and the running Python server.
It does not use Twilio or ngrok, and ignores VOICE_MODE (which only controls the
phone transport). Gemini usage is subject to the project's free-tier availability
and quotas; the application does not enable billing or upgrade any account.

1. Start `uvicorn app.main:app --reload --port 8000` in the project virtual environment.
2. Open http://localhost:8000/talk in Safari, Chrome, or another browser with microphone support.
3. Click **Start talking**, then allow microphone access for localhost.
4. Wait for TechTwin's greeting. Say hello, then talk over its reply to test interruption.
5. Use **Stop the computer** to dispatch an immediate stop, or **End conversation**
   to disconnect, release the microphone, and stop any computer task.

Both sides' transcripts appear on the page and the shared event bus. The Gemini
key stays on the server. Audio uses PCM16 at 16 kHz into Gemini and PCM16 at
24 kHz out, without the telephone audio conversion. The microphone is resampled
continuously in an AudioWorklet and browser speech playback is scheduled locally.

This first browser demo accepts only same-origin localhost connections, not
remote phone/ngrok browsers. Remote access needs a user authentication flow
before it can safely control the shared computer. Headphones can help if the
laptop's speakers cause echo. A page refresh or closed tab ends the session.
The computer helper must still be connected by Dhaush for actual browser actions.

Checks completed: 29 automated tests, a successful Live session using the local
key, and a real `/ws/voice` session that received Gemini greeting audio,
transcripts, and an end-of-audio marker. Actual microphone/speaker interaction
still needs the user's hardware check.

## Account requirement: upgraded Twilio Voice

Twilio's current trial experience blocks `<Stream>`, including the Media Stream
needed by both echo mode and Gemini Live. Use an upgraded account with its own
Voice-capable number. The number displayed under Try out Voice is a trial number;
after upgrading, use the purchased number and configure its incoming-call webhook.
See https://www.twilio.com/docs/usage/trials/try-out-voice#blocked-verbs.

During the local trial test, ngrok received POST /voice from TwilioProxy/1.1
without X-Twilio-Signature, and the app correctly returned 403. Disabling signature
validation would not remove the trial's Stream restriction. Keep validation enabled.

## 1. Start the server

From this project folder:

```sh
source .venv/bin/activate
# On another machine, first: python3 -m venv .venv
python -m pip install -r requirements-dev.txt
cp -n .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000. You should see `TechTwin is running`.
Python 3.11+ is supported; development tests ran on Python 3.14.

## 2. Test the phone line with an echo

1. In another terminal, run `ngrok http 8000`.
2. Edit `.env`: set `PUBLIC_BASE_URL` to ngrok's HTTPS address (no path),
   `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` from your Twilio console, and
   `VOICE_MODE=echo`. Keep `TWILIO_VALIDATE_SIGNATURES=true`.
3. Restart uvicorn after editing `.env`.
4. In Twilio Console → Phone Numbers → your number → Voice configuration,
   set **A call comes in** to Webhook, HTTP POST, and `https://YOUR-NGROK-HOST/voice`.
5. Call your Twilio number. You should hear “Hi, this is TechTwin,” then your
   own voice echoed back. Hang up when this works.

The server verifies the Twilio signature against `PUBLIC_BASE_URL`, so it must
match the address configured in Twilio. If ngrok's address changes, update both.
The Try out Voice trial flow cannot run this streaming test; use the upgraded
account's number. Never paste API keys in chat or commit `.env`.

## 3. Switch to Gemini conversation

1. Set `GEMINI_API_KEY` in `.env`, and change `VOICE_MODE=gemini`.
2. Leave `GEMINI_LIVE_MODEL=gemini-2.5-flash-native-audio-preview-12-2025`
   initially. It remains listed in the Live API documentation; availability and
   quota depend on your Google project. You can change the model without changing code.
3. Restart the server and call again. TechTwin should ask what you need help with.
4. Talk over its reply: its queued speech should stop. Say “stop”: the code
   sends `stop_task` immediately when that word arrives in the caller transcript.
   Recognition/network latency still requires a live check.
5. Look at http://localhost:8000/api/state to inspect transcript and call events.
   Shrey's dashboard can connect to `/ws/dashboard`; when his `static/` files are
   added, restart the server and open `/dashboard`.

If Gemini fails to connect, the call closes and the dashboard receives a short
error. Check model access, quota, and the key, then retry. Calls are limited to
10 minutes and only one call is allowed at a time because the browser is shared.
The dashboard endpoints are intended for the local hackathon demo; the ngrok
origin also exposes them, so avoid sharing that address beyond your team.

## 4. Browser integration for Dhaush

The shared command bridge is implemented in `app/integration.py` and subscribed
by the FastAPI lifespan. Do not add a second voice_command listener.
After initializing the real TaskRunner at application startup, register it:

```python
from app.integration import attach_runner

# runner = your initialized TaskRunner, with its visible browser ready
attach_runner(runner)
```

The runner must implement the async API in BACKEND_HANDOFF.md: start(goal),
confirm(), cancel(), stop(), reset(), describe(). start() schedules the task and
returns its ID promptly. It must never await the full browser task. stop() must
cancel the browser loop within one second. The bridge cancels in-flight commands
when a stop arrives, and both dashboard controls and voice use the same event path.
Expose `latest_screenshot` as JPEG bytes (or a get_screenshot() method returning
bytes) for `/api/screenshot`. Never publish screenshot bytes on the JSON event bus.

Publish the established task events, screenshots, approval questions and results,
blocks and completion summaries to `bus`. The runner owns the safety checks and
pending-approval state. It must refuse confirmation when no step is pending and
refuse a second task while one is running. The bridge does not simulate actions.

The dashboard now serves Shrey's real UI at `/dashboard`, restores its state on
reconnect, and exposes `/api/start_task`, `/api/confirm`, `/api/cancel`, `/api/stop`,
`/api/reset` and `/api/screenshot`. Controls are local-only until authentication
is added. Without a runner, task controls return a visible 503 explanation.
Reset still clears the dashboard when no runner is connected. `/talk` and the
dashboard link to each other, so keep both open during the demo.

Internal events: voice_command carries request_id (string or null), name,
arguments and call_sid. voice_command_result carries request_id and a JSON result
with ok. Null request IDs are stop notifications that need no reply. Voice gets
a failure if no command result arrives within two seconds.

Call/task events are recorded under `logs/<date>/<call-or-task-id>.jsonl`.
Audio is never logged. Transcripts and task goals are recorded for the demo;
keep these local. The directory is gitignored. Run `python scripts/stats.py`
to summarize real task durations/outcomes. Unsafe actions require human review;
the script does not manufacture a zero count.

As of the last GitHub check on November 14, origin/main contains the dashboard
and plan but not app/task_runner.py or app/safety.py, and there are no separate
branches or open pull requests. Full voice-to-browser testing is waiting for
that implementation. Supermemory remains deferred until this flow works.

## 5. Run the automated checks

```sh
source .venv/bin/activate
python -m pytest -q
```

Tests do not use paid APIs, ngrok, or a real phone. They check G.711 codewords,
audio rates and pitch, frame pacing, interrupted playback, stop words, signed
webhooks, hangup cleanup, command responses, and a mocked Gemini session.

Reference docs checked during implementation:

- https://ai.google.dev/gemini-api/docs/live
- https://ai.google.dev/gemini-api/docs/live-guide
- https://ai.google.dev/gemini-api/docs/live-tools
- https://www.twilio.com/docs/voice/media-streams/websocket-messages
- https://www.twilio.com/docs/usage/security

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

Checks completed: 23 automated tests, a successful Live session using the local
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

The original handoff requires module communication through `app/events.py`.
Voice never imports `task_runner`. Add a listener during server startup, and
unsubscribe during shutdown. This is an integration sketch, not installed code:

```python
from app.events import bus

async def on_voice_command(event):
    if event['type'] != 'voice_command':
        return
    name, args = event['name'], event['arguments']
    # Methods must return promptly. start() schedules its loop in the background.
    try:
        if name == 'start_task':
            task_id = await runner.start(args['goal'])
            result = {'ok': True, 'task_id': task_id, 'message': 'Started'}
        elif name == 'confirm_action':
            await runner.confirm()
            result = {'ok': True}
        elif name == 'cancel_action':
            await runner.cancel()
            result = {'ok': True}
        elif name == 'stop_task':
            await runner.stop()
            result = {'ok': True}
        elif name == 'describe_screen':
            result = {'ok': True, 'description': await runner.describe()}
        else:
            result = {'ok': False, 'message': 'Unknown command'}
    except Exception:
        result = {'ok': False, 'message': 'The computer could not do that step.'}
    if event['request_id'] is not None:
        await bus.publish('voice_command_result', request_id=event['request_id'], result=result)

unsubscribe = bus.subscribe(on_voice_command)
```

New internal events (the dashboard may ignore them):

- `voice_command`: `request_id` (string or null), `name`, `arguments`, `call_sid`.
- `voice_command_result`: matching `request_id`, `result` (JSON object with `ok`).

A null request ID is an immediate stop notification (stop word or hangup),
with no reply needed. Keep listeners quick; never await an entire browser task
inside a listener. Cache screen descriptions; expensive work should be scheduled
outside event callbacks. Commands without a result time out after two seconds
with “The computer helper is not connected yet.” A timed-out command must not
be queued for later execution. There is no browser listener yet.

Publish the handoff's existing `step`, `needs_approval`, `blocked`, and
`task_finished` events to trigger spoken updates. Completed steps are narrated at
most every four seconds; scrolls are skipped. Safety checks and tracking pending
approvals remain the runner's responsibility. Both transcript sides accumulate
streaming text and mark final bubbles. `agent_speaking` ends on Twilio's playback
acknowledgment or interruption, rather than when Gemini finishes generating.

Shared glue implemented here: `app/main.py`, `app/events.py`, `/api/state`, and
`/ws/dashboard`. Browser startup, screenshot endpoints, dashboard task buttons,
and call-log files remain integration work for the team. The event history is
bounded in memory and is not a durable log.

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

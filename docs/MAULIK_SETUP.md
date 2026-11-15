# TechTwin: phone-style browser demo

## Run it

From the project folder:

```sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
uvicorn app.main:app --port 8000
```

Put `GEMINI_API_KEY` in the local `.env`. Do not put it in source files or chat.
Our current free setup uses:

```dotenv
COMPUTER_USE_MODEL=gemini-3.1-flash-lite
DESCRIBE_MODEL=gemini-3.1-flash-lite
BROWSER_AUTOSTART=true
HEADLESS=false
MAX_TASK_SECONDS=120
MAX_TASK_STEPS=25
DEV_REPLAY=false
LOG_EVENTS=true
```

The server starts accepting requests, then launches a separate visible Chromium
with a fresh profile. It does not control your Safari, Chrome personal profile,
or native apps. Wait for **Laptop helper connected** on the phone page.

1. Open http://localhost:8000/talk and click **Call Agent 1**.
2. Allow microphone access for localhost.
3. Say: “Please find and play a Ranveer Brar dal recipe on YouTube.”
4. Confirm the repeated goal. Wait for the playback question, then say “Yes, go ahead.”
5. Open http://localhost:8000/dashboard to see the same transcript, real browser
   screenshot, steps, approvals and blocks.
6. **Stop task** or a spoken “stop” cancels the running task. **End call** releases
   the microphone and sends a stop. **Start over** on the dashboard resets Chromium.

Use modest speaker volume or headphones to reduce echo. Keep the helper browser
visible so judges can see it working. Only one conversation/task runs at a time.

## What is simulated, and what is real?

The phone shell is simulated. It does not dial a telephone number. Microphone
input, Gemini Live replies, browser actions, screenshots, approval handling and
logs are real. Gemini Live remains the conversation layer; Flash-Lite reasons
over screenshots and calls browser functions. The dedicated computer-use preview
returned zero free quota on our project. The earlier Flash preview worked, but
its 20-request daily free allowance was exhausted during rehearsal.

Free quotas and model availability depend on the Google project. Do not enable
billing just to run this demo. If a model is unavailable, show the actual recorded
run and explain the failure. The app does not silently replace the real agent
with a scripted success. See Google's pricing and rate-limit documentation:
https://ai.google.dev/gemini-api/docs/pricing
https://ai.google.dev/gemini-api/docs/rate-limits

The Twilio streaming transport remains in the code, but the current Twilio trial
blocks Stream. A real phone deployment needs an upgraded account/Voice number and
a live telephone test. Keep `TWILIO_VALIDATE_SIGNATURES=true`.

## Safety check for the presentation

End the voice call, then open the dashboard. Click **Start over**, then **Show safety
check**. The real runner opens `/static/safety-demo.html`, a clearly labeled local
page with a disabled password field. The guard must block before typing, and the
dashboard must show the red banner. There is no real account or submitted form.

The guard also blocks payments, card fields, unsupported sites and human-verification
challenges. It asks before important actions, including opening a YouTube video.
Voice approval requires a fresh spoken affirmative after the pending question;
a model's confirm_action call alone is not consent. Dashboard approval is the
explicit backup. Real-site challenges require human help, not automatic solving.

## Integration details for the team

The real `app.task_runner.runner` is initialized and registered with
`attach_runner(runner)` during server startup. Voice and dashboard controls use
one shared command bridge. Do not add a second voice_command listener.

Preserved interfaces: `bus.state`, `bus.subscribe` (returns an unsubscribe function),
`bus.unsubscribe`, `dashboard.set_screenshot`, `screenshots.set_latest` and
`dashboard.hooks`. The handoff event names stay unchanged. No production hook
publishes a fake successful task when the helper is missing.

The browser starts in a background startup task because its local start page is
served by this same app. Awaiting that page before HTTP startup can deadlock.
State is reduced once, before event listeners; dashboard refresh retains task and
approval state. Screenshots share the runner's in-memory JPEG store.

Controls are localhost-only until user authentication exists. Do not expose laptop
control to arbitrary ngrok visitors. Browser audio travels as PCM16 at 16 kHz in,
24 kHz out; phone audio conversions apply only to Twilio.

## Logs, checks and rehearsal

Call/task events are stored under `logs/<date>/<call-or-task-id>.jsonl`. Audio and
API keys are not logged; transcripts and task goals are. Keep logs local. The
folder and `.env` are gitignored. Task IDs are unique across server restarts.

```sh
python -m pytest -q
node --test tests/voice/browser_ui.test.cjs
python scripts/stats.py
```

The test suite includes real Chromium interaction checks. The statistics command
reports logged durations/outcomes and steps after a guard block; that narrow
metric does not prove that all possible unsafe actions were prevented.

The terminal runner is also available:

```sh
python scripts/try_task.py "Go to YouTube and find a dal recipe"
```

`--demo`, `/api/dev/replay` and dashboard practice mode are scripted development
helpers. They must be introduced as simulations and are not proof of real model
success. Dev replay is disabled by default and its events are excluded from call
logs. Supermemory remains optional and unimplemented. Five-person usability tests,
a backup recording and Devpost submission still require the team.

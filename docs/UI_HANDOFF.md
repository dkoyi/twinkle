# UI handoff for Dhanush

The latest integration includes the phone, real Gemini voice, guarded browser
runner, dashboard, and streamed browser preview. Run the backend as described in
MAULIK_SETUP.md; use your own local `.env`.

## UI files

- `voice_demo/index.html`, `style.css`, `talk.js`: phone, conversation, microphone,
  and the retained dashboard view.
- `static/dashboard.html`, `dashboard.css`, `dashboard.js`: dashboard inside the
  phone page, also available directly at `/dashboard`.
- `/talk#call` and `/talk#dashboard` switch views without replacing the phone
  document. Keep its audio context and WebSocket alive while changing views.

## Behaviors to preserve

- Dashboard navigation must not open another phone tab or reload an active call.
  The embedded Talk link posts `techtwin:show-call` to its same-origin parent.
- `/ws/voice` owns microphone/audio transport. End call must release microphone,
  playback, audio context, timers, and socket, and stop the backend task.
- `/api/voice/status` includes `active_call`. A new page must show End call for
  an existing conversation instead of offering a duplicate call.
- `POST /api/voice/end` takes `{ "call_sid": "..." }`; send the specific ID so
  a stale page cannot end a newer call. Controls require same-origin localhost.
- Use the supplied screenshot URL. Preview images come from Chrome's frame
  stream; do not add repeated browser screenshot captures or frame fade effects.
- Keep the previous preview visible until the next image is decoded.
- Clear requests start immediately. Important actions still require fresh
  approval; passwords, payments, and unsupported sites remain blocked.
- Keep the browser-phone simulation disclosure visible.

## Checks

```sh
.venv/bin/pytest -q tests
node --test tests/voice/browser_ui.test.cjs
```

Latest checks: 125 Python tests, including 14 real Chromium tests, and 6
JavaScript lifecycle tests passed. See VALIDATION.md for scope and limitations.
Manual UI acceptance: start a call, switch views several times, return to the
same call, end it from either view, and verify silence and microphone release.

Secrets, raw call logs, and local demo recordings are gitignored. The reviewed
Hyperframes evidence bundle remains on Maulik's machine.

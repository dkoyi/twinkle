# Demo validation — November 14, 2026 (Phoenix)

Validated on the combined Maulik voice + Dhanush browser + Shrey dashboard branch.

- 117 Python tests passed, including 9 real Chromium tests; no skipped browser tests.
- 3 JavaScript phone lifecycle checks passed.
- A real Gemini screenshot/function-tool agent completed a YouTube recipe search
  in 15.2 seconds and 3 browser steps before its preview-model quota was exhausted.
- With the free Flash-Lite model, a controlled synthesized caller requested the
  prepared family recipe shortcut, confirmed the goal, and said yes after the
  playback question. The runner opened the real YouTube recipe. The call flow
  took 59.5 seconds; the browser task took 31.2 seconds. Its event trace records
  approval_result approved=true by=voice before the click. The helper recording
  contains the resulting video content; native inspection saw playback at 12 seconds.
- The real runner opened the local password demonstration and was blocked before
  typing. The field is disabled and has no real account.
- A live Stop API request cancelled an active model/runner task in 0.0028 seconds.
  This measures API/runner cancellation, not microphone-to-stop latency.

The local evidence kit lives under demo-artifacts/2026-11-14 (gitignored). It contains
recordings, screenshots, actual Gemini reply audio, a synthetic-caller label,
transcript timings and reports for a Hyperframes handoff. Do not copy .env or raw
private call logs into it.

Known failures retained in the evidence summary: Google verification challenge,
zero free quota for the dedicated Computer Use preview, the Flash preview's
20-request daily cap, and an earlier approval handoff timeout fixed by direct
handling of completed affirmative caller transcripts.

Not verified or implemented: a real telephone call, arbitrary native-app control,
five-person usability testing, a five-run success rate, Supermemory, Devpost
submission, or a guarantee of future API quota and network availability. Phone
shell and family shortcuts are clearly prepared demo context. The reasoning,
conversation, browser action and safety checks run live.

## November 15 follow-up: human call failure

The human caller's request reached start_task, but both attempts failed in 0.0
seconds with zero browser steps. The preview had stopped updating before the
call. The old runner suppressed the underlying exception, so the exact original
cause remains unconfirmed; do not report that call as a success.

Changes: clear requests start without a goal-confirmation yes; the helper can
reopen a closed browser or last tab; its connected status reflects browser
liveness; preview polling survives closed windows; model clients stay open
through approval and close when the task ends. Unexpected runner exceptions now
produce a local diagnostic traceback.

Verification after restart: 120 Python tests passed (including 11 real Chromium
tests and new browser-recovery/client-lifetime regressions), plus 3 JavaScript
phone tests. A real Gemini browser task opened youtube.com in one step and 32.6
seconds, with no pending approval. A separate real Gemini Live request, supplied
as text, called start_task('Open YouTube') after a brief acknowledgment without
a second yes. This separate check does not establish microphone end-to-end
success; a fresh human phone-demo call remains to be verified.

Evidence: demo-artifacts/2026-11-15/youtube-live-state.json and
live-voice-direct-request.json. These controlled results contain no private
human-call transcript and are separate from the November 14 Hyperframes ZIP.

## November 15 follow-up: call controls and navigation

Dashboard navigation now uses a single retained iframe inside the phone page;
returning to the phone preserves its WebSocket, microphone, timer, and End call
control. The embedded dashboard's Talk link returns to the parent view. Browser
Back/Forward between these views changes only the hash. Leaving the page closes
its call; restoring a cached page cleans up its old audio state.

The status endpoint exposes the active browser call ID. A newly opened phone
page shows End call for an older page's conversation instead of starting a
second call. The same-origin localhost end endpoint targets that specific ID,
waits for call cleanup, and ignores stale IDs. Teardown cancels voice workers and
awaits runner stop before releasing ownership. Stop also pauses browser media.

Helper screenshots are serialized and unchanged images retain their URL; both
UIs avoid redisplaying that same frame. The helper keeps one tab when following
new-tab links. Recovery launches Chromium only on an explicit task when the
helper was closed; there is no recurring restart loop. Test browser launches
are headless. Updated asset URLs avoid reuse of the old cached UI.

Verification: 111 non-browser Python tests, 13 real Chromium tests, and 6
JavaScript lifecycle tests passed. Browser tests cover repeated concurrent
screenshots without replacing Chromium or adding tabs, last-tab/window recovery,
and replacing helper tabs. JS tests cover five dashboard/call round trips during
one active socket, ending from the dashboard, ending an older page's call, page
exit, permission races, microphone denial, and audio resource cleanup. The real
website's embedded dashboard navigation and its return link were checked in the
in-app browser. A fresh human microphone rehearsal is still separate from these
controlled checks.

A control-only connection to the real Gemini voice service also reached
voice_ready. Ending it through the HTTP endpoint returned in 0.036 seconds and
status showed no active call afterward. No microphone samples were sent or
recorded in this check. Evidence: live-server-hangup-check.json in the November
15 local evidence folder.

## November 15 follow-up: visible Chrome blinking

The earlier fix still captured the visible helper through Playwright every two
seconds. Replace that path with Chrome DevTools Page.startScreencast: previews
read the most recent JPEG pushed by Chrome and never call page.screenshot or
Page.captureScreenshot. Frame acknowledgments bound streaming work. Model
screenshots use Page.captureScreenshot directly, only when a task needs a fresh
PNG, without Playwright's temporary screenshot preparation. The stream follows
replacement tabs and is detached on shutdown/recovery. Protocol reference:
https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-startScreencast

The dashboard decodes the next frame before swapping it into view and no longer
cross-fades live images. Duplicate frames do not publish screenshot events.
The phone no longer requests a redundant timestamped image after each step.
Updated asset versions ensure the new display code is loaded.

Validation: 14 real Chromium tests passed, including a new regression that
changes the page, observes an updated streamed image, then reads the preview ten
times with no Page.captureScreenshot, no Emulation commands, no page.screenshot,
and zero window resize events. Existing 111 other Python tests and 6 JS lifecycle
tests passed; the 22 task-runner tests were rerun after event deduplication.
This verifies the capture behavior, not a human observation of macOS brightness
or a guarantee against unrelated GPU/display flicker. Reports are saved in the
November 15 local evidence folder with stream-preview filenames.

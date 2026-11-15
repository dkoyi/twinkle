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

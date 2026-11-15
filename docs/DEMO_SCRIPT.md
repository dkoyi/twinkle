# TechTwin — live demo and backup plan

## Before judges arrive

- Run the app with the project virtual environment: `uvicorn app.main:app --port 8000`.
- Wait for the visible Chromium window to open. Keep it visible; it uses a fresh profile.
- Open http://localhost:8000/talk and http://localhost:8000/dashboard.
- The phone page must show **Laptop helper connected**. Allow its microphone when calling.
- Keep speakers modest, or use headphones for the person speaking, to reduce echo.
- Start over from the dashboard before each rehearsal. Close any previous Agent 1 call.
- Use `COMPUTER_USE_MODEL=gemini-3.1-flash-lite` for this project's free-tier setup.
  The dedicated computer-use preview returned zero free quota on our project; the
  older Flash preview has a low daily free allowance.
- Have a screen recording of an actual successful run ready. Practice mode is a
  simulation and must be introduced as such; it is not evidence of a completed live task.

## Three-minute script

**0:00–0:20 — the problem**

“My grandmother can make a phone call, but a simple computer task can leave her
waiting for help. TechTwin gives her a patient voice that can guide the browser.”

**0:20–0:35 — explain the demo honestly**

“This phone interface is simulated in the browser. The voice conversation, Gemini
reasoning, and actions in this separate browser window are live. Telephone
transport is implemented, but needs paid Twilio access and a live phone test.”

**0:35–1:45 — real voice to real browser**

Click **Call Agent 1**. After the greeting, say:

“Please play the dal recipe saved on my family shortcuts.”

Confirm the repeated goal. The prepared demo start page contains a real YouTube recipe link. Let the model choose that shortcut from the screen; the click is still live and approval-gated. When Agent 1 asks
whether to play the video, say **“Yes, go ahead.”** Point to the real browser,
the screenshot, the transcript, and the approval banner.

If search is slow, use the dashboard Start task field as the disclosed backup:
“Go directly to https://www.youtube.com/results?search_query=Ranveer+Brar+dal+recipe
and show the search results. Do not open a video.” This tests the actual model;
it is not a scripted playback. Do not solve verification challenges automatically.

**1:45–2:15 — safety**

End the voice call. Click **Start over**, then **Show safety check** on the dashboard.
Say: “This is a local demonstration page with a disabled password field. It has no
real account. Our guard sees the field and stops before any typing.”

Wait for the real runner to open that page and produce the red blocked banner.
Do not say that this is a real checkout, real bank account, or completed purchase.

**2:15–2:45 — how it works and measured proof**

“Gemini Live handles the conversation. A Gemini vision model reads screenshots
and calls browser tools through Playwright. A separate guard checks each action.
Important actions need approval; passwords, payments and unsupported sites stop
the task. The family can see the same steps and transcript.”

The controlled synthesized-caller rehearsal completed in 59.5 seconds overall (31.2 seconds in the browser task). This is one rehearsal, not a human usability study. Use only numbers actually measured. Run `python scripts/stats.py` for logged
outcomes and durations. The post-block step count is one narrow check, not proof
that every possible unsafe action was prevented. Do not claim five user tests
until five people have actually tested the product.

**2:45–3:00 — close**

“Today we are demonstrating the complete browser voice path. Next comes a verified
telephone deployment and more testing with the people who would use this.”

## Recovery

- No voice: check microphone permission, end the call, and call again. Use dashboard
  Start task for a clearly disclosed no-voice fallback.
- Helper unavailable: check the server log and Chromium installation; restart once.
- Model quota/network error: stop, explain the failure, and show the recorded run.
- Verification/CAPTCHA: stop for human help. Never claim the agent bypassed it.
- Pending approval: say yes clearly after the question, or use the dashboard Yes
  button as a disclosed backup. Silence never approves a real action.
- “Stop” or Stop task halts the task. Hang-up also sends a stop. Reset clears the
  task and returns the helper browser to its start page.

## Remaining human work before submission

1. Have five people try a short task; record completion time, failures and feedback.
2. Record the successful browser voice flow and safety check.
3. Rehearse within three minutes on the venue network.
4. Fill Devpost with the actual demo scope, architecture, results and limitations.
5. Submit before the event deadline in the team's implementation plan.

Supermemory is optional after the core demo passes. It is not implemented and
must not be claimed in the pitch yet. Do not promise arbitrary native-app access:
this implementation controls a browser on the laptop.

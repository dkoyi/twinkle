# Build steps — one milestone at a time

How to use this file: do the milestones **in order**. For each one, copy the **Prompt** into Claude Code in VS Code, let it work, then do the **Check**. Don't start the next milestone until the check passes. If something breaks, tell Claude Code exactly what you saw (copy the error text).

Suggested split for a team of 3–4:
- **Person A (phone + voice):** milestones 1–3
- **Person B (browser agent):** milestones 4–5, working in parallel with A
- **Person C (dashboard + design):** milestone 6, in parallel. Design the screen in Claude Design first.
- **Everyone:** milestones 7–9

---

## Milestone 0: project setup

**Prompt:**
> Read CLAUDE.md and docs/SPEC.md. Set up the Python project: create a virtual environment, a requirements.txt with the packages listed in CLAUDE.md, the folder structure from CLAUDE.md with empty placeholder files, a .gitignore that excludes .env and the virtual environment, and install Playwright's Chromium. Then explain to me, in plain words, how to activate the environment and run the server. Don't build features yet.

**Check:** `uvicorn app.main:app --reload` starts, and opening http://localhost:8000 shows any "hello" page.

---

## Milestone 1: the phone answers

**Prompt:**
> Build the Twilio phone line. Add a /voice webhook that returns TwiML which first says "Hi, this is TechTwin" and then connects a bidirectional Media Stream to our /media WebSocket. In /media, log every Twilio event (connected, start, media, stop) to the console. Then walk me step by step through: starting ngrok on port 8000, and pasting the ngrok https URL + /voice into my Twilio phone number's "A call comes in" webhook setting.

**Check:** calling the Twilio number, you hear "Hi, this is TechTwin", and the console prints `media` events while you talk.

---

## Milestone 2: the phone talks back (echo test)

**Prompt:**
> In /media, decode the incoming μ-law audio and send it straight back to Twilio as outbound media, so the caller hears their own voice (an echo test). Put the audio helpers in app/audio.py: μ-law to 16-bit PCM, PCM to μ-law, and resampling between 8 kHz, 16 kHz and 24 kHz.

**Check:** on a call, you hear yourself echoed back clearly.

---

## Milestone 3: real conversation with the voice brain

**Prompt:**
> Connect the call to the Gemini Live API. Check the current Gemini Live docs for the right model name and the audio formats. Stream caller audio in (converted to 16 kHz PCM) and Gemini's spoken replies out (converted to 8 kHz μ-law). Give it the system instructions from the "Voice and tone" section of CLAUDE.md. Support barge-in: if the caller starts talking, stop playing Gemini's audio. Add a live transcript of both sides to the console.

**Check:** you can have a natural spoken conversation on the phone. It greets you and asks what you need help with.

---

## Milestone 4: the browser agent (no phone yet)

**Prompt:**
> Build app/task_runner.py: a loop that drives a visible Chromium browser with Playwright using a computer-use model. Check the current docs for Gemini's Computer Use model (fallback: Claude computer use). Each loop takes a screenshot, asks the model for the next action toward the goal, runs it, and repeats until done or after 25 steps. Emit a progress event after every step. Add a small test script, scripts/try_task.py, that runs one goal from the command line, e.g. "Go to YouTube and play a Ranveer Brar dal recipe video".

**Check:** `python scripts/try_task.py "..."` opens a browser you can watch, and it completes the task.

---

## Milestone 5: the safety guard

**Prompt:**
> Build app/safety.py following the "Safety guard rules" in docs/SPEC.md. The task runner must call it before every action. Return one of: allow, ask_first(reason), block(reason). For ask_first, pause the loop until confirm() or cancel() is called. Add ALLOWED_DOMAINS to .env. Extend scripts/try_task.py so ask_first prompts me in the terminal with y/n. Write simple tests for the rules.

**Check:** the task "Buy an iPhone on apple.com" stops at checkout. The "join meeting" task asks before clicking Join.

---

## Milestone 6: the dashboard

**Prompt:**
> Build the dashboard at http://localhost:8000/dashboard: a single HTML page that updates live over a WebSocket. Layout: left, a big live browser screenshot; right, the call transcript (caller and TechTwin, large text); bottom, the step list with timestamps and status icons (done, waiting for approval, blocked). Show a large yellow banner when waiting for approval and a red one when blocked. It must be readable from 2 metres away, with friendly, calm colours and no technical words. [Paste or describe the design from Claude Design here.]

**Check:** running try_task.py, the dashboard shows each step and screenshot live.

---

## Milestone 7: connect everything

**Prompt:**
> Connect the voice brain to the task runner using the tools in CLAUDE.md: start_task, confirm_action, cancel_action, describe_screen, stop_task. The task runner's progress events should be spoken to the caller in plain words (not every tiny step: summarise). Approvals must be asked on the phone and answered by voice. Everything should also show on the dashboard. The caller saying "stop" must halt the browser immediately.

**Check:** call the number, ask for the YouTube task, approve by voice, and watch it happen on screen and on the dashboard.

---

## Milestone 8: make it demo-proof

**Prompt:**
> Make the demo reliable. Add: (1) a "demo mode" in .env that pre-opens the browser to a clean start page, (2) clear spoken recovery if any step fails ("That didn't work, let me try another way"), (3) a timeout so no task runs more than 2 minutes, (4) a reset button on the dashboard, (5) a log file of every call, with timings, for our "measured proof" numbers. Then list the riskiest failure points and fix the top 3.

**Check:** run each demo task 5 times in a row. It should succeed at least 4 out of 5.

---

## Milestone 9: proof + polish

- Test with 5 people who didn't build it (ideally someone over 50). Record the time to finish and any problems.
- Record a backup video of a full successful call (Devpost video is optional, but it saves you if the Wi-Fi fails).
- Fill in Devpost as you go, using `docs/DEMO_SCRIPT.md`.

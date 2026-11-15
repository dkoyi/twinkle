# TechTwin — product spec

## The problem

Older adults get stuck on small computer tasks: joining a video call, opening an attachment, finding a form. They wait days for a grandchild, or they get help from "tech support" scammers who take over their computer. Screen-sharing help needs a family member to be free at that moment, and video tutorials move too fast.

## The pitch (one line)

**"Call a number, say what you need, and watch your own computer do it, slowly and safely, while a kind voice explains every step."**

## Who it's for

- **Primary:** Grandma (70+), comfortable with a phone call, nervous about computers.
- **Secondary:** the family member who usually gets the "can you help me?" call. They can watch the dashboard from anywhere.

## User flow

1. Grandma calls the TechTwin number.
2. TechTwin greets her: "Hi, I'm TechTwin. What would you like help with on your computer today?"
3. She says: "My grandson sent me a Zoom link, I want to join."
4. TechTwin repeats the goal back ("You'd like to join your grandson's Zoom meeting. Is that right?") and waits for "yes".
5. The browser on her computer comes forward. TechTwin narrates each step: "I'm opening your email… I can see a message from Rahul with a link… I'm opening it now."
6. Before the important click: "There's a blue button that says Join. Shall I press it?" She says "yes", and TechTwin presses it.
7. If a password or payment field appears, TechTwin stops and explains it won't do that part.
8. When it's done: "You're in the meeting now. Is there anything else?"
9. The dashboard (for the family member and the judges) shows the transcript, the live screen, the step list with timestamps, and every approval.

## Demo tasks (no logins needed; pick the 2 most reliable)

1. **Join a meeting from a link:** open a Zoom or Google Meet link in the browser and join as a guest, entering the name "Grandma".
2. **Find information:** "What time does the CVS on Mill Avenue close today?" It searches, opens the page, and reads the answer aloud.
3. **Play a video:** "Play the cooking video my daughter told me about, the one with Ranveer Brar's dal." It searches YouTube, picks the right result, and plays it full-screen.
4. **Safety demo:** "Buy me the new iPhone." It goes to a store page, reaches checkout, **stops** and explains why.

Use task 1 or 3 for the main demo and task 4 to show safety.

## Components

| Component | Job | Tools |
| --- | --- | --- |
| Phone line | Receive the call, stream audio both ways | Twilio Programmable Voice + Media Streams, ngrok for a public URL |
| Voice brain | Listen, talk, decide when to call tools | Gemini Live API (real-time audio + function calling) |
| Audio converter | Convert between Twilio's phone audio and Gemini's audio format | numpy (or `audioop-lts`) |
| Task runner | Drive a visible browser toward the goal | Computer-use model (Gemini Computer Use, or Claude computer use) + Playwright |
| Safety guard | Check every proposed action before it runs | Our own rules (`app/safety.py`) |
| Dashboard | Show transcript, live screen, steps, approvals | FastAPI WebSocket + plain HTML |

## How the voice brain and task runner talk

- The voice brain calls `start_task(goal)`. The task runner starts its loop in the background.
- The task runner sends **progress messages** ("Opening YouTube", "Found the video") to the voice brain, which speaks them in plain words.
- When the safety guard flags an action as important, the task runner **pauses** and emits `needs_approval("Click the Join button")`. The voice brain asks the caller, then calls `confirm_action()` or `cancel_action()`.
- When the safety guard flags a forbidden action (password, payment, a site not on the allowlist), the task runner stops and emits `blocked(reason)`.

## Safety guard rules

- **Ask first** if the target element's text or label matches: join, send, submit, buy, pay, order, delete, remove, download, install, allow, accept, sign up, confirm.
- **Block** if the page has a password input, a credit-card field (autocomplete `cc-*`, or labels like "card number" or "CVV"), or a URL path with checkout, payment or billing. Also block any domain not on `ALLOWED_DOMAINS`.
- **Stop** immediately if the caller says "stop", "cancel" or "no no no".

## What "done" looks like (Best Overall bar)

- A judge calls from their own phone, asks for a task, and it completes live in under 90 seconds.
- The safety stop works live.
- The dashboard is clean and readable from 2 metres away: large text, big screenshot, clear step list.
- Measured proof: "We tested 5 people. They completed tasks in X seconds on average, with 0 unsafe actions."

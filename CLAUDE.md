# TechTwin — project brief for Claude Code

Claude Code reads this file automatically. It explains what we're building, how, and the rules.

## What TechTwin is (one sentence)

An older person calls a phone number and says what they need ("help me join my grandson's Zoom"), and an AI agent does it **on their own computer's browser**, step by step, explaining slowly out loud and asking before anything important.

## Context

- Built at **sunhacks 2026** (ASU, Nov 14–15). Goal: **Best Overall**.
- Judged on Design, Originality, Functionality, Complexity. A **3-minute live demo** of the working project is judged, not slides.
- Hackathon rule: all code is written during the event. Don't copy in old projects.
- The team is mostly **non-technical**. When you explain something to us, use plain words, define every term once, and give one step at a time. After each change, tell us exactly how to test it (what to run, what we should see).

## Architecture (keep it this simple)

```
 Grandma's phone ──call──> Twilio phone number
                               │  (live audio over a WebSocket, "Media Streams")
                               ▼
                    TechTwin server (Python, FastAPI)  <──── ngrok public URL
                     │            │              │
       voice brain   │            │ task runner  │  live dashboard
   (Gemini Live API: │            │ (computer-use│  (web page: transcript,
    listens + talks, │            │  model +     │   live screenshot,
    calls tools)     │            │  Playwright  │   steps, approvals)
                     └──── tools ─┘  browser)    │
```

1. **Phone line:** Twilio Programmable Voice. Incoming call → our `/voice` webhook returns TwiML `<Connect><Stream>` → Twilio streams call audio to our `/media` WebSocket (8 kHz μ-law, base64, JSON `media` events). We stream audio back the same way.
2. **Voice brain:** Gemini Live API (real-time speech in and out, with tool calling). Audio must be converted: Twilio 8 kHz μ-law → 16 kHz 16-bit PCM for Gemini input; Gemini output (24 kHz PCM) → 8 kHz μ-law for Twilio. Use numpy (or `audioop-lts` on Python 3.13+) for conversion.
3. **Task runner:** a computer-use model drives a **real, visible Chromium browser** through Playwright: screenshot → model proposes an action (click, type, scroll, open URL) → safety check → execute → repeat. Default model: Gemini's Computer Use model. Fallback: Claude computer use. **Check the current docs for the exact model name before writing code.**
4. **Dashboard:** a local web page (served by the same FastAPI app, updates live over a WebSocket) showing the call transcript, the latest browser screenshot, the step list, and any pending "May I click Join?" approval. This is what judges watch.

**Stack:** Python 3.11+, FastAPI + uvicorn, `twilio`, `google-genai`, `playwright`, `python-dotenv`, `numpy`. Front end: plain HTML + a little JavaScript (no build step).

## Tools the voice brain can call

- `start_task(goal: str)` — begin a browser task, e.g. "join the Zoom meeting at this link".
- `confirm_action()` / `cancel_action()` — the caller said yes or no to a pending step.
- `describe_screen()` — say in plain words what's on the screen right now.
- `stop_task()` — stop everything immediately.

## Safety rules (non-negotiable, and part of the pitch)

1. **Ask before important clicks.** Anything that joins, sends, submits, buys, deletes or downloads pauses and asks the caller "Shall I click Join?" Only a spoken "yes" continues.
2. **Never touch passwords or payments.** If a password field, card field or checkout page appears, stop and say: "This part needs you or a family member. I won't type passwords or payment details."
3. **Allowlist of sites** for the demo (set in `.env`). Anything else is blocked with a spoken explanation.
4. **Stop word.** Saying "stop" at any time halts the agent.
5. **Everything is visible.** The browser window is never hidden, and every step is logged on the dashboard.

## Voice and tone

Speak slowly, warmly, in short sentences. Describe what you're doing before you do it ("I can see a blue button that says Join. I'm going to press it now."). Never use technical words with the caller.

## Coding conventions

- Small files with clear names: `app/main.py`, `app/twilio_stream.py`, `app/voice_brain.py`, `app/audio.py`, `app/task_runner.py`, `app/safety.py`, `app/dashboard.py`, `static/dashboard.html`.
- Secrets only in `.env` (never commit it). `.env.example` lists every variable.
- Log every step to the console *and* the dashboard.
- Build in the milestone order in `docs/BUILD_STEPS.md`. Each milestone must work on its own before the next one starts.
- Prefer working and simple over clever. The demo must not crash.

## Key docs

- `docs/SPEC.md`: full product spec, user flow, demo tasks
- `docs/BUILD_STEPS.md`: milestones with the exact prompt to give Claude Code for each
- `docs/DEMO_SCRIPT.md`: the 3-minute demo, backup plan, Devpost text

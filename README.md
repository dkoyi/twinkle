<div align="center">

<img src=".github/readme/logo.svg" width="110" alt="TechTwin logo: Twinkle's round glasses, one teal lens and one butter-yellow lens, with a yellow star above">

# TechTwin

### Call Twinkle. Say what you need. Watch your own computer do it, safely.

A phone call for people who are not comfortable with computers. You talk to **Twinkle**, a friendly voice helper, and she does the task on your own laptop where you can see it, asking you first before anything important.

[![Live preview](https://img.shields.io/badge/preview-twinkle--khaki.vercel.app-0F5A60?style=for-the-badge)](https://twinkle-khaki.vercel.app)
![sunhacks 2026](https://img.shields.io/badge/sunhacks-2026-F4B52E?style=for-the-badge)
![Voice](https://img.shields.io/badge/voice-Gemini%20Live-2F6F73?style=for-the-badge)
![Stack](https://img.shields.io/badge/stack-FastAPI%20·%20Playwright%20·%20JS-55635b?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-1E2A2B?style=for-the-badge)

<img src=".github/readme/phone.png" width="860" alt="The TechTwin call page: a phone calling Twinkle beside the laptop's live screen">

</div>

---

## Why it exists

Most of us have a parent or grandparent who phones us to ask "how do I open YouTube again?" Help apps assume you can already use a computer. A phone call doesn't: everybody knows how to make one.

With TechTwin you call Twinkle and talk to her like a person. She listens, works on your own computer in a browser you can watch, explains what she is doing in plain words, and stops to ask before she presses anything that matters. If something goes wrong, she says so plainly instead of guessing.

## How it works

```mermaid
sequenceDiagram
    autonumber
    actor U as Person on the phone
    participant P as Phone page (/talk)
    participant S as TechTwin server (FastAPI)
    participant G as Gemini Live (voice)
    participant A as Browser agent (Playwright)
    participant D as Dashboard + floating Twinkle

    U->>P: Presses "Call Twinkle" and speaks
    P->>S: Microphone audio over /ws/voice
    S->>G: Streams audio
    G-->>S: Twinkle's voice + a tool call ("open YouTube, search cooking")
    S-->>P: Twinkle's voice plays back
    S->>A: Start task
    loop Each step
        A->>A: Screenshot, decide next action
        A->>S: Safety check (allowed / ask first / blocked)
        S-->>D: step, screenshot (/ws/dashboard)
    end
    A-->>S: Needs a yes ("Shall I press play?")
    S-->>G: Twinkle asks out loud
    S-->>D: Yes / No buttons appear
    U->>G: "Yes"
    G->>S: Approve
    S->>A: Continue
    A-->>S: Done
    S-->>D: task_finished
    G-->>U: "All done, the video is playing."
```

```mermaid
flowchart LR
    phone["Phone page<br/>(/talk)"] -- "audio /ws/voice" --> server["FastAPI server<br/>app/main.py"]
    server <-- "Gemini Live API" --> gemini["Gemini Live<br/>voice + tools"]
    server --> runner["Task runner<br/>app/task_runner.py"]
    runner --> safety["Safety guard<br/>app/safety.py"]
    runner --> browser["Visible Chromium<br/>app/browser.py (Playwright)"]
    server -- "events /ws/dashboard" --> dash["Dashboard<br/>/dashboard"]
    server -- "events" --> widget["Floating Twinkle<br/>on every page"]
    dash -- "Yes / No /api/confirm" --> server
    widget -- "Yes / No" --> server
```

**Safety is in the code, not just the prompt.** Every action passes `app/safety.py`. Payments, passwords, downloads and anything unknown are blocked. Important clicks ("play", "send", "buy") need a spoken or tapped yes first. The browser is visible the whole time, and **Stop** works at any moment.

## What you see

<div align="center">
<img src=".github/readme/dashboard.png" width="860" alt="The dashboard: the laptop's live screen, the conversation word for word, and each step Twinkle took">
</div>

| Part | What it does |
|---|---|
| **Phone page** `/talk` | A phone you call Twinkle on. Live voice through Gemini, the conversation as text, the laptop's screen beside it. |
| **Dashboard** `/dashboard` | The laptop's live screen, every step Twinkle took, the transcript, big Yes / No when she asks first, Stop and Start over. |
| **Floating Twinkle** | The mascot stays in the corner of every page and says in one sentence what is happening. She shows Yes / No when she is asking. |

The phone in the browser stands in for a real phone line for the demo. The server also has a Twilio Media Streams path (`app/twilio_stream.py`) for real phone numbers.

## Run it

You need Python 3.11+, a free Gemini API key (aistudio.google.com) and Chromium for Playwright.

```sh
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium
cp .env.example .env            # put your GEMINI_API_KEY in it
uvicorn app.main:app --port 8000
```

Open **http://localhost:8000/talk** on the same laptop (the microphone needs `localhost`), press **Call Twinkle**, allow the microphone and say something like *"Open YouTube and find a video on how to make chai."* A Chromium window opens and Twinkle works in it.

No key? Open `/dashboard?demo=dal` to watch a scripted practice call. The [Vercel preview](https://twinkle-khaki.vercel.app) is the front end only, with no voice or laptop control, because those need the local server.

Tests: `python -m pytest -q`.

## Repository

```
app/            FastAPI server: voice (Gemini Live), task runner, browser agent, safety guard, events
static/         Dashboard, brand layer (fonts, logo, mascot, floating Twinkle)
voice_demo/     The phone page (/talk)
tests/          pytest suite, including a guard that the UI keeps every element id the scripts use
scripts/        Static build for the Vercel preview, demo helpers
docs/           Spec, front end guide, backend handoff, demo script
```

More detail: [docs/FRONTEND.md](docs/FRONTEND.md) (pages, brand, floating Twinkle) · [docs/BACKEND_HANDOFF.md](docs/BACKEND_HANDOFF.md) (event contract, safety rules, task runner API)

## Built with

Python, FastAPI, WebSockets, Gemini Live (native audio), Gemini (browser reasoning), Playwright, HTML, CSS, JavaScript, Vercel.

## Team

Built at **sunhacks 2026** by
- **Dhaush**: browser agent, safety guard, front end and brand
- **Maulik**: phone and voice (Gemini Live, audio, call lifecycle)
- **Shrey**: dashboard UI

## License

[MIT](LICENSE)

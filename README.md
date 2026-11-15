# TechTwin

Call a number, say what you need, and watch your own computer do it, slowly and safely.

Built at sunhacks 2026 (ASU).

## Free voice demo

Set `GEMINI_API_KEY` in `.env`, run the server, then open
http://localhost:8000/talk on the laptop. Click **Call Agent 1** on the simulated phone and allow the
microphone. This browser demo uses Gemini directly through our server and does
not need Twilio or ngrok. Free-tier usage is subject to your Google project's
quota. Browser control still needs the team's task runner integration.

See [Maulik's setup guide](docs/MAULIK_SETUP.md) for details. Remote browser voice
access is disabled until authentication is added; use localhost for this demo.

## Team

- **Shrey** — dashboard UI (`static/`)
- **Maulik** — phone + voice (Twilio, audio, Gemini Live)
- **Dhaush** — browser agent + safety guard

Backend people: start with `docs/BACKEND_HANDOFF.md`.

## Setup for teammates (one time)

1. **Install:** Python 3.11+ (python.org), VS Code (code.visualstudio.com), and the **Claude Code** extension in VS Code (Extensions tab → search "Claude Code").
2. **Install ngrok** (ngrok.com, free account). It gives your laptop a public web address so Twilio can reach it.
3. **Open this folder in VS Code** (File → Open Folder → `techtwin`).
4. **Copy `.env.example` to `.env`** and fill in the keys (ask whoever made the accounts).
5. **Open Claude Code** in VS Code and start with Milestone 0 in `docs/BUILD_STEPS.md`.

## What's in this folder

| File | What it's for |
| --- | --- |
| `CLAUDE.md` | Project brief that Claude Code reads automatically: architecture, safety rules, tone |
| `docs/SPEC.md` | Full product spec, user flow, demo tasks |
| `docs/BUILD_STEPS.md` | Milestones in order, each with a prompt to paste into Claude Code and a check |
| `docs/DEMO_SCRIPT.md` | 3-minute demo, judge Q&A, Devpost text |
| `docs/BACKEND_HANDOFF.md` | Backend handoff for Maulik and Dhaush: who owns which files, the event contract the dashboard expects, model names, traps |
| `.env.example` | Every secret/setting the app needs (copy to `.env`) |

## Accounts you need

- **Twilio** (twilio.com): upgraded account and a Voice-capable phone number. The current trial blocks `<Stream>`, which our live audio requires. See [trial restrictions](https://www.twilio.com/docs/usage/trials/try-out-voice#blocked-verbs).
- **Gemini API key** (aistudio.google.com): free.
- **ngrok** (ngrok.com): free.

## Phone backend (Maulik)

The phone and voice implementation is ready for local testing. Follow
[Maulik's setup guide](docs/MAULIK_SETUP.md) to run the server, test the phone
with echo mode, then enable Gemini conversation. That guide also documents the
event interface Dhaush connects to the browser agent.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp -n .env.example .env
uvicorn app.main:app --reload --port 8000
```

Run the offline checks with `python -m pytest -q`. Real phone calls require
Twilio credentials and an ngrok address in `.env`; Gemini mode also needs a
Gemini API key. Browser automation and Shrey's dashboard are separate team work.

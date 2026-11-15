# TechTwin

Call a number, say what you need, and watch your own computer do it, slowly and safely.

Built at sunhacks 2026 (ASU).

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

- **Twilio** (twilio.com): free trial and a phone number. On a trial, verify every phone that will call it.
- **Gemini API key** (aistudio.google.com): free.
- **ngrok** (ngrok.com): free.

# TechTwin — 3-minute demo, backup plan, Devpost text

## Setup at the table

- Laptop with the browser on the left half and the dashboard on the right half (or on a second screen facing the judges).
- The TechTwin phone number printed big on a card: "Call TechTwin: (xxx) xxx-xxxx".
- Phone charged and on speaker, in case a judge's phone can't call (a Twilio trial can only call verified numbers; add about $20 of credit to accept any caller).
- The backup video ready to play.

## The 3 minutes

**0:00–0:20: the hook (one speaker)**
> "My grandmother has a computer she's scared to touch. Every time she needs to join a call, she waits days for one of us, or worse, she lets a 'tech support' stranger take over her screen. So we built TechTwin."

**0:20–1:40: the live call (a judge does it)**
> "Call this number and ask it to do something on this laptop."

The judge asks, for example, "Play a dal recipe video by Ranveer Brar." Everyone watches the browser move while the voice explains. TechTwin asks "Shall I press play?", and the judge says yes.

**1:40–2:15: the safety moment**

A teammate asks: "Buy me the new iPhone." TechTwin goes to the store, reaches checkout, **stops** and says it won't handle payments. The dashboard shows a red "Blocked: payment page" banner.

**2:15–2:45: how it works + proof**
> "A phone call streams through Twilio to Gemini, which talks with you. A computer-use agent drives a real browser, and a safety guard checks every single click: it asks before important clicks and never touches passwords or payments. We tested it with 5 people: average task time X seconds, zero unsafe actions."

**2:45–3:00: the close**
> "No app to install, no screen to share: just a phone call. TechTwin gives every grandparent a patient grandchild on call."

## Judge questions to prepare for

- *"Isn't it dangerous to let AI control a computer?"* → The safety guard: ask-first, no passwords or payments, an allowlist, a stop word, everything visible.
- *"How is this different from remote support?"* → No stranger, no screen sharing, works with just a phone call, available 24/7.
- *"What if the AI clicks the wrong thing?"* → It narrates before acting, important clicks need a spoken "yes", and "stop" halts everything.
- *"How would this work on Grandma's own computer?"* → A small helper app the family installs once; the phone number links to her computer.

## Devpost text (fill in as you go)

**Inspiration:** [your real grandparent story, 2–3 sentences]

**What it does:** Call a phone number, say what you need, and TechTwin does it on your own computer's browser, explaining every step out loud and asking before anything important.

**How we built it:** Twilio Media Streams → FastAPI server → Gemini Live API (real-time voice + tool calling) → computer-use agent with Playwright → safety guard → live dashboard over WebSockets.

**Challenges:** [audio format conversion, latency, making the agent reliable, the safety rules]

**Accomplishments:** [your test numbers]

**What's next:** a one-click helper app for Grandma's computer, more languages (Hindi, Bengali, Spanish), and a family "watch-along" view.

**Built with:** python, fastapi, twilio, gemini-live-api, playwright, websockets, ngrok

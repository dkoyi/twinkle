# Front end guide

Two pages, one brand layer, one floating helper. Maulik's call and audio code is untouched; this is the look.

| URL | What it is |
|---|---|
| `/talk` | The phone page. A large phone mockup that makes the real Gemini voice call, the live laptop preview, the conversation. This is the main demo. |
| `/dashboard` | The live dashboard (also shown inside `/talk#dashboard`). Direct visits get the floating Twinkle. `?demo=dal` or `?demo=iphone` plays a practice call with no backend. |

## Files

| File | Job |
|---|---|
| `static/brand/brand.css` | Fonts, colour tokens (`:root`), the logo styles, Twinkle's animation CSS, the floating widget's look. Re-theme here. |
| `static/brand/twinkle.js` | The mascot rig (`TT.twinkle.mount(el).set('thinking')`, eight moods), icons, and the logo (`TT.markSVG`: glasses plus a star). |
| `static/brand/widget.js` | The floating Twinkle. Same place and look on every page, one plain sentence of what is happening, Yes and No while she is asking. Skipped inside an iframe. |
| `static/brand/favicon.svg` | The star as the app icon. |
| `static/fonts/` | Baloo 2 (display) and Atkinson Hyperlegible Next (body), self-hosted so the demo never depends on venue wifi. |
| `voice_demo/index.html`, `style.css` | The phone page. `talk.js` (Maulik's) drives it by element id. |
| `static/dashboard.html`, `dashboard.css` | The dashboard. `dashboard.js` drives it by element id. A refresh block at the end of `dashboard.css` carries the brand look. |

## The floating Twinkle

She sits bottom right on every page. Her ring and mood follow the state: idle, listening, working, asking (butter, with big Yes and No), stopped for safety (red), done. After a few seconds of quiet she tucks her message away and speaks up again when something happens.

Events: `/dashboard` sets `<body data-feeds-widget>` and dispatches `techtwin:event` for every event (so practice mode works too). Any other page opens its own read-only `/ws/dashboard` connection. She only ever writes with Yes and No (`POST /api/confirm`, `/api/cancel`), the same calls the dashboard makes.

Optional spots she fills if the page has them: `#phoneTwinkle` (the phone's contact photo; its mood follows `body[data-phase]` and `#orb.speaking`) and `#emptyMascot` (the dashboard's empty screen).

## Do not rename these (a test guards them)

`tests/test_brand_ui.py` fails if an element id used by `talk.js` or `dashboard.js` disappears from its page. Restyle freely; keep the ids. Also keep: no duplicate call on view switch, End call releases the microphone, use the supplied screenshot URL, keep the simulation disclosure visible.

## Brand

Wordmark "TechTwin"; helper "Twinkle". Logo: her two lenses (teal and butter) with a yellow star above the bridge. The star is also the favicon. Fonts and palette are tokens in `brand.css`. A fuller brand pass (final logo, palette direction) is being designed separately; when it lands, replace the `:root` block, `TT.markSVG` and `favicon.svg`.

UX rules for people who are not comfortable with computers: 20px minimum text, plain words, one obvious action, nothing important without a plain question first, colour never the only signal, motion off under `prefers-reduced-motion`.

## Running and deploying

Real demo: `.env` with `GEMINI_API_KEY`, `uvicorn app.main:app --port 8000`, open `http://localhost:8000/talk` on that computer (microphone needs `localhost`).
UI only, no key: `BROWSER_AUTOSTART=false uvicorn app.main:app --port 8000`.
Static preview on Vercel (design review only: no voice, no laptop control, because a static host has no WebSocket or helper):
```
python scripts/build_static.py --working      # or no flag to build exactly what is committed
cd deploy/techtwin && vercel deploy --prod --yes --scope dkoyis-projects
```
`deploy/` and `.vercel/` are gitignored.

# Front end guide

| URL | Page | Files |
|---|---|---|
| `/`, `/talk` | The phone: only an iPhone call. Contact card, then the call screen. | `static/phone.html`, `phone.css`, `phone.js`, `voice.js` |
| `/dashboard` | Watch view: the laptop's screen, every step, the transcript, Yes / No, Stop. | `static/dashboard.html`, `dashboard.css`, `dashboard.js` |
| `/family` | Phone-width view for a relative. | `static/family.html` (uses `dashboard.js`) |
| `/help` | Microphone, setup, connection and 404 help. | `static/help.html` |
| `/classic` | The earlier all-in-one call page. | `voice_demo/` |

Brand and character pages: `static/logo.html` (colours, logos, icons), `static/twinkle.html` (moods), `static/components.html`.

## How the call works on the page

`phone.js` only shows the call. `voice.js` does the real call and exposes `window.TwinkleVoice = { start, stop, mute, speaker }`:
microphone through an AudioWorklet (`/voice-demo/microphone.js`) to `/ws/voice`, Twinkle's audio played back as 16-bit PCM.
The phone goes live when the server publishes `call_started` on `/ws/dashboard`, and ends on `call_ended`. If the microphone is blocked it opens `/help#mic`.
Approvals, safety stops and the transcript are on the dashboard; Twinkle asks for approvals out loud on the call.

## Practice mode (no backend)

`/talk?practice` and `/dashboard?demo=1` (or `?demo=iphone` for the safety stop) play a scripted call from `static/demo.js`.
The Vercel build sets `window.TT_NO_WS` on the phone page, so the public preview always runs the practice call.

## Brand

Colours are the tokens in `:root` at the top of `static/dashboard.css`. Fonts are Baloo 2 and Atkinson Hyperlegible Next, self-hosted in `static/fonts/`.
Logos, the star favicon and Twinkle's animated and still moods are in `static/assets/`. Twinkle is a still picture on the phone and animated on the website pages.

## Guard

`tests/test_brand_ui.py` checks that every page is served, its assets load, and every element id a script looks up exists on its page.

## Deploy the preview

```
python scripts/build_static.py --working
```
Vercel runs this itself on every push to `main` (see `vercel.json`).

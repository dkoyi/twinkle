"""The safety guard. Every action goes through `check()` before it runs.

Rules, first match wins (docs/BACKEND_HANDOFF.md section 4.2):
  1. BLOCK  a site that is not on ALLOWED_DOMAINS (current page, or where we're navigating).
  2. BLOCK  a page with a password box, card fields, or a checkout/payment/billing address.
            Also never type something that looks like a card number.
  3. ASK    before clicking something that joins, sends, buys, deletes, downloads...
            or before Enter on a form whose button says one of those.
  4. ALLOW  everything else.

`reason` and `question` are spoken to the caller and shown on the banners, so they are
written in plain words ("This page asks for a password"), never "password input detected".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

from app.actions import Action, px
from app.settings import get_settings

# Words on a button/link that need a spoken "yes" first.
ASK_WORDS = [
    "join", "send", "submit", "buy", "pay", "order", "delete", "remove", "download", "install",
    "allow", "accept", "sign up", "confirm", "purchase", "add to bag", "add to cart",
    "continue to checkout",
]

PATH_RE = re.compile(r"(?:^|[/_.-])(checkout|payment|payments|billing|pay)(?:$|[/_.?-])", re.I)
CARD_NUMBER_RE = re.compile(r"(?:\d[ -]?){13,19}")

PASSWORD_REASON = "This page asks for a password. This part needs you or a family member."
CARD_REASON = ("This page asks for card details. This part needs you or a family member. "
               "I won't type payment details.")
PAYMENT_URL_REASON = ("This looks like a payment page. This part needs you or a family member. "
                      "I won't handle payments.")
TYPED_CARD_REASON = "That looks like a card number, and I won't type payment details."

# ---- what we look at on the page (run inside the browser) ----
PAGE_PROBE_JS = """
() => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const inputs = [...document.querySelectorAll('input, textarea')].filter(vis);
  const cardRe = /(card\\s*number|cvv|cvc|security\\s*code|expir(y|ation)|exp\\.?\\s*date)/i;
  const password = inputs.some(i => (i.type || '').toLowerCase() === 'password');
  const card = inputs.some(i =>
    (i.getAttribute('autocomplete') || '').toLowerCase().startsWith('cc-') ||
    cardRe.test([i.name, i.id, i.placeholder, i.getAttribute('aria-label')].join(' ')) ||
    (i.labels && [...i.labels].some(l => cardRe.test(l.innerText || ''))));
  const challenge = /verify you are human|unusual traffic from your computer|not a robot|complete the captcha/i.test(document.body?.innerText || '');
  return {password, card, challenge};
}
"""

ELEMENT_PROBE_JS = """
([x, y]) => {
  const el = (x === null || y === null) ? document.activeElement : document.elementFromPoint(x, y);
  if (!el) return {text: '', form: '', tag: ''};
  const grab = (e) => [e.innerText, e.getAttribute('aria-label'), e.value, e.title, e.getAttribute('alt')]
      .filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim().slice(0, 200);
  const target = el.closest('button, a, [role=button], [role=link], input, label, summary') || el;
  const form = target.closest('form') || el.closest('form');
  const formText = form
    ? [...form.querySelectorAll('button, input[type=submit], [role=button]')].map(grab).join(' ').slice(0, 300)
    : '';
  return {text: grab(target), form: formText, tag: target.tagName.toLowerCase(), href: target.href || ''};
}
"""


@dataclass
class Verdict:
    kind: Literal["allow", "ask_first", "block"]
    reason: str = ""      # spoken + shown on the banner
    question: str = ""    # for ask_first: "Shall I press Join?"
    label: str = ""

    @property
    def allowed(self) -> bool:
        return self.kind == "allow"


ALLOW = Verdict("allow")


# ---------- helpers ----------
def _ask_regex() -> re.Pattern:
    words = ASK_WORDS + get_settings().ask_first_extra
    parts = [re.escape(w).replace(r"\ ", r"\s+") for w in words]
    return re.compile(r"\b(" + "|".join(parts) + r")\b", re.I)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def host_allowed(url: str, allowed: list[str] | None = None) -> bool:
    """True if `url` is on the allowlist. `www.youtube.com` passes for `youtube.com`;
    `evil-youtube.com` does not."""
    allowed = allowed if allowed is not None else get_settings().allowed_domains
    parsed = urlparse(url if "://" in url or url.startswith(("about:", "data:")) else "https://" + url)
    if parsed.scheme in ("about", "data", "blob", "chrome-error", "chrome"):
        return True  # blank page, our own start page, browser error pages
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    return any(host == d or host.endswith("." + d) for d in allowed)


def _domain_reason(url: str) -> str:
    host = _host(url if "://" in url else "https://" + url) or "that website"
    return f"I can only visit a short list of safe websites, and {host} isn't one of them."


async def _probe(page: Any, js: str, arg: Any = None) -> dict:
    try:
        return (await page.evaluate(js, arg) if arg is not None else await page.evaluate(js)) or {}
    except Exception:
        return {}  # page is mid-navigation: no signal, so no false alarm


async def label_for(action: Action, page: Any, viewport: tuple[int, int] | None = None) -> str:
    """Plain label of the thing under a click ("Join Meeting"), or '' if unknown."""
    if not action.has_point:
        return ""
    w, h = viewport or (get_settings().viewport_w, get_settings().viewport_h)
    info = await _probe(page, ELEMENT_PROBE_JS, [px(action.nx, w), px(action.ny, h)])
    text = (info.get("text") or "").strip()
    return text if len(text) <= 40 else text[:37].rstrip() + "..."


# ---------- the checks ----------
async def check_page(page: Any) -> Verdict:
    """Is the page we are on right now somewhere we must not be? Run after every action."""
    url = getattr(page, "url", "") or ""
    if not host_allowed(url):
        return Verdict("block", _domain_reason(url))
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and PATH_RE.search(parsed.path or ""):
        return Verdict("block", PAYMENT_URL_REASON)
    probe = await _probe(page, PAGE_PROBE_JS)
    if probe.get('challenge') or urlparse(url).path.startswith('/sorry/'):
        return Verdict('block', 'This website needs a person to complete a verification check. Please ask a family member for help.')
    if probe.get("password"):
        return Verdict("block", PASSWORD_REASON)
    if probe.get("card"):
        return Verdict("block", CARD_REASON)
    return ALLOW


async def check(action: Action, page: Any, viewport: tuple[int, int] | None = None) -> Verdict:
    """Decide what to do about one proposed action."""
    v = await check_page(page)
    if not v.allowed:
        return v
    sd = action.safety_decision
    if isinstance(sd, dict) and str(sd.get('decision', '')).lower() in ('block', 'blocked', 'deny'):
        return Verdict('block', 'This step was blocked to keep you safe.')

    if action.kind == "navigate":
        if not action.url or not host_allowed(action.url):
            return Verdict("block", _domain_reason(action.url or ""))
        if PATH_RE.search(urlparse(action.url if "://" in action.url else "https://" + action.url).path or ""):
            return Verdict("block", PAYMENT_URL_REASON)
        if video_url(action.url):
            return Verdict('ask_first', 'Opening this link will play a video.', question='Shall I play this video?')

    if action.kind == "type" and action.text and CARD_NUMBER_RE.fullmatch(action.text.strip()):
        return Verdict("block", TYPED_CARD_REASON)

    ask = _ask_regex()
    w, h = viewport or (get_settings().viewport_w, get_settings().viewport_h)

    # Clicks: look at what is under the pointer.
    if action.kind in ("click", "double_click", "type") and action.has_point:
        info = await _probe(page, ELEMENT_PROBE_JS, [px(action.nx, w), px(action.ny, h)])
        text = (info.get("text") or "").strip()
        if video_url(info.get('href', '')):
            return Verdict('ask_first', 'Opening this link will play a video.', question='Shall I play this video?')
        m = ask.search(text)
        if m:
            label = text if 0 < len(text) <= 40 else m.group(0)
            return Verdict("ask_first", f"This could {m.group(0).lower()} something.",
                           question=f"Shall I press {label}?", label=label)

    # Enter (typed with press_enter, or the Enter key): look at the focused form's buttons.
    wants_enter = (action.kind == "type" and action.press_enter) or \
                  (action.kind == "key" and (action.keys or "").lower() in ('enter', 'space'))
    if wants_enter:
        coords = [px(action.nx, w), px(action.ny, h)] if (action.kind == "type" and action.has_point) else [None, None]
        info = await _probe(page, ELEMENT_PROBE_JS, coords)
        if video_url(info.get('href', '')):
            return Verdict('ask_first', 'Opening this link will play a video.', question='Shall I play this video?')
        m = ask.search((info.get("form") or '') + ' ' + (info.get('text') or ''))
        if m:
            return Verdict("ask_first", f"This could {m.group(0).lower()} the form.",
                           question="Shall I send this form?", label=m.group(0))

    # The model itself asked for confirmation (its own built-in safety check).
    sd = action.safety_decision
    if isinstance(sd, dict) and str(sd.get("decision", "")).lower().replace("-", "_") in ("require_confirmation", "ask"):
        return Verdict("ask_first", sd.get("explanation") or "This step needs your okay.",
                       question="Is it okay if I carry on with this step?")

    return ALLOW


def video_url(url):
    parsed = urlparse(url or '')
    host = (parsed.hostname or '').lower()
    return (host == 'youtu.be' or
            ((host == 'youtube.com' or host.endswith('.youtube.com')) and
             (parsed.path == '/watch' or parsed.path.startswith(('/shorts/', '/embed/')))))

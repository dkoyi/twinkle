"""The model adapter: screenshot + goal in, next actions out.

This is the ONLY file that knows how a computer-use model talks. The rest of the app sees
`Action`s (app/actions.py). To change model or API, change this file only.

Handoff said `propose_action(screenshot, goal, history) -> Action`. Computer-use APIs are
conversations (each reply carries the new screenshot), so the provider keeps that
conversation itself:

    provider = make_provider()
    proposal = await provider.start(goal, first_screenshot_png)
    ... run the actions ...
    proposal = await provider.respond([ActionResult(...)])      # repeat until proposal.done

If the Gemini docs now require a different call (they have an "Interactions API"), only
`GeminiProvider._generate` and `respond` change.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass, field
from typing import Protocol

from app.actions import Action, parse_function_call
from app.settings import get_settings


class ProviderError(Exception):
    """The model could not be reached or answered badly. Message is safe to log."""


@dataclass
class Proposal:
    actions: list[Action] = field(default_factory=list)
    text: str = ""

    @property
    def done(self) -> bool:
        return not self.actions


@dataclass
class ActionResult:
    action: Action
    url: str
    png: bytes
    error: str | None = None          # the action failed or the person said no
    acknowledged: bool = False        # the person said yes to the model's own safety question


class Provider(Protocol):
    async def start(self, goal: str, png: bytes) -> Proposal: ...
    async def respond(self, results: list[ActionResult]) -> Proposal: ...


SYSTEM_PROMPT = """You are TechTwin, helping someone who is not comfortable with computers by \
doing a task for them in a web browser.

- Work step by step. Look at the screen, take the single most useful action, then look again.
- Use one browser tool per turn. All x/y coordinates are normalized from 0 to 1000.
- A tool response includes the current screenshot. Never claim success until the screenshot verifies it.
- Keep going until the task is finished. Do not stop to ask questions: a separate safety \
system asks the person before anything important happens.
- You may ONLY use these websites: {domains}. If the task needs another site, stop and say so.
- Never type passwords, card numbers or other private details. If a page asks for them, stop.
- Prefer searching and clicking the obvious result. Close or ignore cookie banners and pop-ups \
only if they block the page.
- If a visible saved shortcut matches the person's request, use it first. Otherwise, \
for a YouTube task, start directly on YouTube and use its search box. Do not open \
search filters unless the person specifically requested filters.
- When the task is finished, or you cannot continue, reply with ONE short, plain sentence for \
an older person saying what happened, with no technical words and no mention of "pages" or \
"elements" (for example: "The video is playing now.").
"""

# Regular Gemini vision models can use these functions on the free tier. The
# dedicated Computer Use preview has zero free quota on some projects.
FUNCTIONS = [
    {'name': 'navigate', 'description': 'Open an allowed website URL.',
     'parameters': {'type': 'OBJECT', 'properties': {'url': {'type': 'STRING'}}, 'required': ['url']}},
    {'name': 'click_at', 'description': 'Click a point on the screenshot. Coordinates are 0-1000.',
     'parameters': {'type': 'OBJECT', 'properties': {'x': {'type': 'NUMBER'}, 'y': {'type': 'NUMBER'}}, 'required': ['x', 'y']}},
    {'name': 'type_text_at', 'description': 'Click a text field, replace its contents and type. Only press Enter if needed.',
     'parameters': {'type': 'OBJECT', 'properties': {'x': {'type': 'NUMBER'}, 'y': {'type': 'NUMBER'},
                    'text': {'type': 'STRING'}, 'press_enter': {'type': 'BOOLEAN'}}, 'required': ['x', 'y', 'text', 'press_enter']}},
    {'name': 'key_combination', 'description': 'Press keys, e.g. Enter or Control+A.',
     'parameters': {'type': 'OBJECT', 'properties': {'keys': {'type': 'STRING'}}, 'required': ['keys']}},
    {'name': 'scroll_document', 'description': 'Scroll the page up or down.',
     'parameters': {'type': 'OBJECT', 'properties': {'direction': {'type': 'STRING', 'enum': ['up', 'down']},
                     'magnitude': {'type': 'INTEGER'}}, 'required': ['direction']}},
    {'name': 'wait_5_seconds', 'description': 'Wait for a page or video to load.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
    {'name': 'go_back', 'description': 'Go back to the previous page.',
     'parameters': {'type': 'OBJECT', 'properties': {}}},
]


# ---------------------------------------------------------------------------
# Gemini (generate_content + the computer_use tool)
# ---------------------------------------------------------------------------
class GeminiProvider:
    KEEP_SCREENSHOTS = 3

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        from google import genai  # imported here so tests don't need a key

        s = get_settings()
        key = api_key or s.gemini_api_key
        if not key:
            raise ProviderError("GEMINI_API_KEY is missing. Add it to .env.")
        self.client = genai.Client(api_key=key)
        self.model = model or s.computer_use_model
        self.custom_tools = self.model.startswith(('gemini-3', 'gemini-4')) or self.model == 'gemini-2.5-flash'
        self.contents: list = []

    def _config(self):
        from google.genai import types

        domains = ", ".join(get_settings().allowed_domains) or "none"
        tools = ([types.Tool(function_declarations=FUNCTIONS)] if self.custom_tools else
                 [types.Tool(computer_use=types.ComputerUse(environment=types.Environment.ENVIRONMENT_BROWSER))])
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT.format(domains=domains),
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    async def close(self):
        close = getattr(self.client.aio, 'aclose', None)
        if close:
            await close()

    def _prune(self) -> None:
        """Old screenshots are heavy and the model doesn't need them: keep the last few."""
        carriers = []
        for i, c in enumerate(self.contents):
            for p in c.parts or []:
                fr = getattr(p, "function_response", None)
                if (fr is not None and fr.parts) or getattr(p, "inline_data", None) is not None:
                    carriers.append(i)
                    break
        for i in carriers[:-self.KEEP_SCREENSHOTS]:
            for p in self.contents[i].parts or []:
                if getattr(p, "inline_data", None) is not None:
                    p.inline_data = None
                    p.text = "[earlier screenshot removed]"
                fr = getattr(p, "function_response", None)
                if fr is not None and fr.parts:
                    fr.parts = None

    async def _generate(self) -> Proposal:
        self._prune()
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self.client.aio.models.generate_content(
                    model=self.model, contents=self.contents, config=self._config())
                break
            except Exception as exc:  # rate limit / network: back off and retry
                last_exc = exc
                if getattr(exc, 'code', None) == 429:
                    raise ProviderError('The computer helper has reached a service limit. Please try again later.') from None
                if getattr(exc, 'code', None) in (400, 403, 404):
                    raise ProviderError('The computer helper is not available with these settings. Please ask a family member to check them.') from None
                await asyncio.sleep(1.5 * (attempt + 1))
        else:
            raise ProviderError('The browser model could not be reached. Check the configured model and free quota.')

        if not resp.candidates or not resp.candidates[0].content:
            raise ProviderError("The model sent an empty answer.")
        content = resp.candidates[0].content
        self.contents.append(content)

        actions, texts = [], []
        for part in content.parts or []:
            fc = getattr(part, "function_call", None)
            if fc is not None:
                actions.append(parse_function_call(fc.name, dict(fc.args or {}), getattr(fc, "id", None)))
            elif getattr(part, "text", None) and not getattr(part, "thought", False):
                texts.append(part.text)
        return Proposal(actions=actions, text=" ".join(texts).strip())

    async def start(self, goal: str, png: bytes) -> Proposal:
        from google.genai import types

        self.contents = [types.Content(role="user", parts=[
            types.Part(text=goal),
            types.Part.from_bytes(data=png, mime_type="image/png"),
        ])]
        return await self._generate()

    async def respond(self, results: list[ActionResult]) -> Proposal:
        from google.genai import types

        parts = []
        for r in results:
            payload: dict = {"url": r.url}
            if r.error:
                payload["error"] = r.error
            if r.acknowledged:
                payload["safety_acknowledgement"] = "true"
            parts.append(types.Part(function_response=types.FunctionResponse(
                name=r.action.name,
                id=r.action.call_id,
                response=payload,
                parts=[types.FunctionResponsePart(inline_data=types.FunctionResponseBlob(
                    mime_type="image/png", data=r.png))],
            )))
        self.contents.append(types.Content(role="user", parts=parts))
        return await self._generate()


# ---------------------------------------------------------------------------
# A scripted stand-in: lets the loop, the safety guard and the dashboard be
# developed and tested with no API key and no network.
# ---------------------------------------------------------------------------
class ScriptedProvider:
    def __init__(self, proposals: list[Proposal]) -> None:
        self._queue = list(proposals)
        self.seen: list[list[ActionResult]] = []

    async def start(self, goal: str, png: bytes) -> Proposal:
        return self._next()

    async def respond(self, results: list[ActionResult]) -> Proposal:
        self.seen.append(results)
        return self._next()

    def _next(self) -> Proposal:
        return self._queue.pop(0) if self._queue else Proposal(text="All done.")


def make_provider() -> Provider:
    which = os.getenv("COMPUTER_USE_PROVIDER", "gemini").lower()
    if which == "gemini":
        return GeminiProvider()
    raise ProviderError(f"The '{which}' computer-use provider isn't built yet. Use COMPUTER_USE_PROVIDER=gemini.")


# ---------------------------------------------------------------------------
# "What's on the screen?" in plain words (voice tool describe_screen)
# ---------------------------------------------------------------------------
_describe_cache: dict[str, str] = {}


async def describe_screen(png: bytes) -> str:
    key = hashlib.sha1(png).hexdigest()
    if key in _describe_cache:
        return _describe_cache[key]
    s = get_settings()
    if not s.gemini_api_key:
        return "I can see a web page, but I can't read it out loud right now."
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=s.gemini_api_key)
        resp = await client.aio.models.generate_content(
            model=s.describe_model,
            contents=[types.Part.from_bytes(data=png, mime_type="image/png"),
                      "Describe this screen to a 75-year-old in two short sentences. "
                      "No technical words. Say what they could do next."],
        )
        text = (resp.text or "").strip() or "I can see a web page."
    except Exception:
        text = "I can see a web page, but I'm having trouble describing it."
    _describe_cache[key] = text
    return text

"""The task runner: drives the visible browser toward a goal, one safe step at a time.

Public API (docs/BACKEND_HANDOFF.md section 4.1), used by the voice tools and the dashboard:

    from app.task_runner import runner
    task_id = await runner.start("play a dal recipe video")   # returns at once
    await runner.confirm(by="voice")      # the caller said yes
    await runner.cancel(by="voice")       # the caller said no
    await runner.stop()                   # hard stop, well inside one second
    text = await runner.describe()        # plain words about the screen
    await runner.reset()                  # stop + clean start page + clear dashboard

Everything the outside world needs to know is published on the event bus (app/events.py).

Per step:  screenshot -> model proposes -> safety.check -> (ask the person) -> act -> screenshot.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Optional
from uuid import uuid4
from urllib.parse import urlparse

from app import computer_use, safety, screenshots
from app.actions import Action
from app.browser import Browser, BrowserError
from app.computer_use import ActionResult, ProviderError, make_provider
from app.events import EventBus, bus as default_bus
from app.settings import get_settings


class TaskBusy(Exception):
    """A task is already running. The message is safe to say out loud."""


def _clip(text: str, n: int = 40) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _domain(url: str) -> str:
    host = urlparse(url if "://" in url else "https://" + url).hostname or ""
    return host.removeprefix("www.") or "a new page"


def _plain(text: str) -> str:
    """Make the model's closing words safe to speak: no markdown, at most two sentences."""
    text = re.sub(r"[*_`#>]+", "", text or "")
    text = " ".join(text.split())
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return _clip(" ".join(sentences[:2]), 220)


def phrases(a: Action, label: str = "") -> tuple[str, str]:
    """(while it happens, once it's done), in plain words. No technical terms."""
    lab = f"“{_clip(label)}”" if label else ""
    if a.kind in ("click", "double_click"):
        return (f"Clicking {lab}" if lab else "Clicking here"), (f"Clicked {lab}" if lab else "Clicked here")
    if a.kind == "right_click":
        return "Opening a menu", "Opened a menu"
    if a.kind == "hover":
        return "Pointing at something", "Pointed at something"
    if a.kind == "type":
        t = f"“{_clip(a.text or '')}”"
        return f"Typing {t}", f"Typed {t}"
    if a.kind == "scroll":
        d = a.direction if a.direction in ("up", "down", "left", "right") else "down"
        return f"Scrolling {d}", f"Scrolled {d}"
    if a.kind == "navigate":
        d = _domain(a.url or "")
        return f"Opening {d}", f"Opened {d}"
    if a.kind == "key":
        k = (a.keys or "a key").replace("Control", "Ctrl")
        return f"Pressing {k}", f"Pressed {k}"
    if a.kind == "wait":
        return "Waiting a moment", "Waited a moment"
    if a.kind == "back":
        return "Going back", "Went back"
    if a.kind == "forward":
        return "Going forward", "Went forward"
    if a.kind == "drag":
        return "Moving something", "Moved something"
    return "Looking at the screen", "Looked at the screen"


class TaskRunner:
    def __init__(self, browser: Browser, provider_factory=make_provider,
                 event_bus: EventBus = default_bus) -> None:
        self.browser = browser
        self.provider_factory = provider_factory
        self.bus = event_bus
        self._task: Optional[asyncio.Task] = None
        self._counter = 0
        self.task_id: Optional[str] = None
        self.goal: str = ""
        self._approval: Optional[asyncio.Future] = None
        self._pending: Optional[dict] = None
        self._steps = 0
        self._provider = None

    # ------------------------------------------------------------------ public API
    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, goal: str) -> str:
        if self.running:
            raise TaskBusy("I'm already helping with something. Say stop first if you'd like me to change it.")
        goal = " ".join((goal or "").split())
        if not goal:
            raise ValueError("Please tell me what you'd like help with.")
        self._counter += 1
        self.task_id = f"t-{uuid4().hex[:12]}"
        self.goal = goal
        self._steps = 0
        await self.bus.publish("task_started", task_id=self.task_id, goal=goal)
        self._task = asyncio.create_task(self._run(goal, self.task_id))
        return self.task_id

    async def confirm(self, by: str = "voice") -> bool:
        """The person said yes. Returns False if nothing was waiting."""
        return await self._answer(True, by)

    async def cancel(self, by: str = "voice") -> bool:
        """The person said no to the pending step. The task may carry on another way."""
        return await self._answer(False, by)

    async def stop(self) -> None:
        """Hard stop. Cancels the loop wherever it is, including mid-click or mid-approval."""
        task = self._task
        if task and not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=1.0)

    async def describe(self) -> str:
        if not self.browser.started:
            return "My browser isn't open yet."
        try:
            return await computer_use.describe_screen(await self.browser.screenshot_png())
        except BrowserError:
            return "I can't see the screen right now."

    async def reset(self) -> None:
        await self.stop()
        screenshots.clear()
        try:
            await self.browser.reset()
        except BrowserError:
            pass
        await self.bus.publish("reset")

    def snapshot(self) -> dict:
        return {"running": self.running, "task_id": self.task_id, "goal": self.goal,
                "steps": self._steps, "pending": self._pending}

    # ------------------------------------------------------------------ approvals
    async def _answer(self, yes: bool, by: str) -> bool:
        fut = self._approval
        if fut is None or fut.done():
            return False
        fut.set_result(yes)
        await self.bus.publish("approval_result", task_id=self.task_id, approved=yes, by=by)
        return True

    async def _ask(self, n: int, verdict: safety.Verdict) -> bool:
        s = get_settings()
        fut = asyncio.get_running_loop().create_future()
        self._approval = fut
        self._pending = {"step_n": n, "question": verdict.question}
        await self.bus.publish("needs_approval", task_id=self.task_id, step_n=n,
                               question=verdict.question or "Is that okay?", reason=verdict.reason)
        try:
            return await asyncio.wait_for(asyncio.shield(fut), s.approval_timeout_s)
        except asyncio.TimeoutError:
            if not fut.done():
                fut.set_result(False)
                await self.bus.publish("approval_result", task_id=self.task_id, approved=False, by="timeout")
            return False
        finally:
            close = getattr(self._provider, 'close', None)
            if close:
                try:
                    await close()
                except Exception:
                    pass
            self._provider = None
            if not fut.done():
                fut.cancel()  # we were stopped while waiting
            self._approval = None
            self._pending = None

    # ------------------------------------------------------------------ the loop
    async def _run(self, goal: str, task_id: str) -> None:
        t0 = time.monotonic()
        s = get_settings()
        outcome, summary = "failed", "That didn't work out. Let's try again."
        try:
            outcome, summary = await asyncio.wait_for(self._loop(goal, task_id), s.max_task_seconds)
        except asyncio.TimeoutError:
            outcome, summary = "timeout", "That was taking too long, so I stopped."
        except asyncio.CancelledError:
            outcome, summary = "cancelled", "Okay, I've stopped."
        except ProviderError as exc:
            await self.bus.publish("error", where="model", message=str(exc))
            outcome, summary = "failed", "The computer helper is unavailable. Please ask a family member or try again shortly."
        except Exception:  # never let one task take the server down
            await self.bus.publish("error", where="task_runner", message='The computer helper had a problem and stopped safely.')
            outcome, summary = "failed", "Something unexpected happened, so I stopped."
        finally:
            self._approval = None
            self._pending = None
            await self.bus.publish("task_finished", task_id=task_id, outcome=outcome, summary=summary,
                                   duration_s=round(time.monotonic() - t0, 1), steps=self._steps)

    async def _loop(self, goal: str, task_id: str) -> tuple[str, str]:
        s = get_settings()
        provider = self.provider_factory()
        self._provider = provider
        png = await self.browser.screenshot_png()
        await self._show(task_id, 0)
        proposal = await provider.start(goal, png)
        declines = failures = 0

        while True:
            if proposal.done:
                return "done", _plain(proposal.text) or "All done."

            results: list[ActionResult] = []
            for action in proposal.actions:
                if self._steps >= s.max_task_steps:
                    return "failed", "I tried a lot of steps and couldn't finish, so I stopped."
                self._steps += 1
                n = self._steps
                page = self.browser.page
                label = await safety.label_for(action, page)
                doing, did = phrases(action, label)
                point = ({"x": round(action.nx / 1000, 4), "y": round(action.ny / 1000, 4)}
                         if action.has_point else None)
                step = dict(task_id=task_id, n=n, action=action.kind)
                await self.bus.publish("step", summary=doing, status="running",
                                       **({"point": point} if point else {}), **step)

                verdict = await safety.check(action, page)
                if verdict.kind == "block":
                    await self.bus.publish("step", summary=doing, status="failed", **step)
                    await self.bus.publish("blocked", task_id=task_id, reason=verdict.reason, url=_domain(self.browser.url))
                    return "blocked", verdict.reason

                acknowledged, error = False, None
                if verdict.kind == "ask_first":
                    if await self._ask(n, verdict):
                        acknowledged = True
                    else:
                        declines += 1
                        error = "The person said no, so this step was skipped."
                        await self.bus.publish("step", summary="Skipped, as you asked", status="failed", **step)
                        results.append(ActionResult(action, self.browser.url, await self.browser.screenshot_png(),
                                                    error=error))
                        if declines >= 2:
                            return "cancelled", "Okay, I won't do that."
                        continue

                try:
                    await self.browser.execute(action)
                    failures = 0
                    await self.bus.publish("step", summary=did, status="done", **step)
                except BrowserError as exc:
                    failures += 1
                    error = str(exc)
                    await self.bus.publish("step", summary="That didn't work, trying another way",
                                           status="failed", **step)
                    if failures >= 3:
                        return "failed", "I couldn't get that to work, so I stopped."

                png = await self.browser.screenshot_png()
                await self._show(task_id, n)

                after = await safety.check_page(self.browser.page)  # did we land somewhere we mustn't be?
                if after.kind == "block":
                    await self.bus.publish("blocked", task_id=task_id, reason=after.reason, url=_domain(self.browser.url))
                    return "blocked", after.reason

                results.append(ActionResult(action, self.browser.url, png, error=error, acknowledged=acknowledged))

            proposal = await provider.respond(results)

    async def _show(self, task_id: str, n: int) -> None:
        """Send the newest screenshot to the dashboard."""
        try:
            jpeg = await self.browser.screenshot_jpeg()
        except BrowserError:
            return
        url = screenshots.set_latest(jpeg)
        await self.bus.publish("screenshot", task_id=task_id, n=n, url=url, page_url=self.browser.url)


# One module-level browser + runner for the whole server (docs/BACKEND_HANDOFF.md section 4.1).
browser = Browser()
runner = TaskRunner(browser)

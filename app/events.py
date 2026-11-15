"""The shared event bus and live state.

Every module talks to the others ONLY through this file (see docs/BACKEND_HANDOFF.md).
Publish an event from anywhere:

    from app.events import bus
    await bus.publish("step", task_id="t1", n=1, action="click",
                      summary="Opened YouTube", status="done")

The dashboard WebSocket forwards every event to the browser, and `bus.state` keeps a
running snapshot so a page that connects late (or reloads) is never blank.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

Listener = Callable[[dict], Awaitable[None]]

MAX_HISTORY = 500


class State:
    """What the dashboard needs to repaint itself: built purely from events."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.call: dict | None = None
        self.task: dict | None = None
        self.steps: list[dict] = []
        self.transcript: list[dict] = []
        self.pending_approval: dict | None = None
        self.blocked: dict | None = None
        self.screenshot_url: str | None = None

    def apply(self, ev: dict) -> None:
        t = ev.get("type")
        if t == "reset":
            self.reset()
        elif t == "call_started":
            self.call = {"from": ev.get("from"), "call_sid": ev.get("call_sid"), "ts": ev["ts"]}
        elif t == "call_ended":
            self.call = None
        elif t == "transcript":
            who, text, final = ev.get("who"), ev.get("text", ""), bool(ev.get("final", True))
            last = self.transcript[-1] if self.transcript else None
            if last and not last["final"] and last["who"] == who:
                last["text"], last["final"] = text, final  # still being spoken: replace in place
            else:
                self.transcript.append({"who": who, "text": text, "final": final})
        elif t == "task_started":
            self.task = {"id": ev.get("task_id"), "goal": ev.get("goal", ""), "ts": ev["ts"], "finished": False}
            self.steps, self.pending_approval, self.blocked = [], None, None
        elif t == "step":
            row = {"n": ev.get("n"), "summary": ev.get("summary", ""), "status": ev.get("status", "running"),
                   "action": ev.get("action"), "ts": ev["ts"]}
            for i, s in enumerate(self.steps):
                if s["n"] == row["n"]:
                    self.steps[i] = {**s, **row, "ts": s["ts"]}
                    break
            else:
                self.steps.append(row)
        elif t == "screenshot":
            self.screenshot_url = ev.get("url")
        elif t == "needs_approval":
            self.pending_approval = {"question": ev.get("question", ""), "reason": ev.get("reason", ""),
                                     "step_n": ev.get("step_n"), "task_id": ev.get("task_id")}
        elif t == "approval_result":
            self.pending_approval = None
        elif t == "blocked":
            self.blocked = {"reason": ev.get("reason", ""), "url": ev.get("url")}
            self.pending_approval = None
        elif t == "task_finished":
            if self.task:
                self.task.update(finished=True, outcome=ev.get("outcome"), summary=ev.get("summary", ""))
            self.pending_approval = None

    def snapshot(self) -> dict:
        return {
            "call": self.call,
            "task": self.task,
            "steps": self.steps,
            "transcript": self.transcript,
            "pending_approval": self.pending_approval,
            "blocked": self.blocked,
            "screenshot_url": self.screenshot_url,
        }


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[Listener] = []
        self._tasks: set[asyncio.Task] = set()
        self.history: list[dict] = []
        self.state = State()

    def subscribe(self, fn: Listener) -> None:
        if fn not in self._listeners:
            self._listeners.append(fn)

    def unsubscribe(self, fn: Listener) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    async def publish(self, type: str, **data: Any) -> dict:
        event = {"type": type, "ts": time.time(), **data}
        self.state.apply(event)
        self.history.append(event)
        del self.history[:-MAX_HISTORY]
        if type != "screenshot":  # screenshot urls can be huge data URIs in dev
            print(f"[event] {event}")
        for fn in list(self._listeners):
            task = asyncio.create_task(self._safe(fn, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return event

    @staticmethod
    async def _safe(fn: Listener, event: dict) -> None:
        try:
            await fn(event)
        except Exception as exc:  # one bad listener must never break the others
            print(f"[event] listener {getattr(fn, '__name__', fn)} failed: {exc!r}")


bus = EventBus()  # one shared instance: import this everywhere

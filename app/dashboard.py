"""Dashboard routes: live WebSocket, state snapshot, screenshot, and the button endpoints.

Contract: docs/BACKEND_HANDOFF.md section 2. The buttons call into `hooks`; the task
runner and voice code replace these defaults when they are ready:

    from app import dashboard
    dashboard.hooks.confirm = task_runner.confirm
"""
from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import APIRouter, Body, Response, WebSocket, WebSocketDisconnect

from app import screenshots
from app.events import bus

router = APIRouter()


# ---------- latest screenshot (stored by app/screenshots.py) ----------
def set_screenshot(jpeg: bytes) -> str:
    """Kept for compatibility: store the newest screenshot, return its URL."""
    return screenshots.set_latest(jpeg)


@router.get("/api/screenshot")
async def get_screenshot() -> Response:
    data = screenshots.get_latest()
    if data is None:
        return Response(status_code=204)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ---------- hooks the buttons call (defaults just publish events so the UI is testable) ----------
async def _confirm(by: str = "dashboard") -> None:
    p = bus.state.pending_approval
    if p:
        await bus.publish("approval_result", task_id=p.get("task_id"), approved=True, by=by)


async def _cancel(by: str = "dashboard") -> None:
    p = bus.state.pending_approval
    if p:
        await bus.publish("approval_result", task_id=p.get("task_id"), approved=False, by=by)


async def _reset() -> None:
    await bus.publish("reset")


async def _start_task(goal: str) -> None:
    await bus.publish("task_started", task_id="dev", goal=goal)


async def _stop() -> None:
    await _cancel()


class Hooks:
    confirm: Callable[..., Awaitable[None]] = staticmethod(_confirm)
    cancel: Callable[..., Awaitable[None]] = staticmethod(_cancel)
    reset: Callable[..., Awaitable[None]] = staticmethod(_reset)
    start_task: Callable[[str], Awaitable[None]] = staticmethod(_start_task)
    stop: Callable[..., Awaitable[None]] = staticmethod(_stop)


hooks = Hooks


# ---------- JSON API ----------
@router.get("/api/state")
async def api_state() -> dict:
    return {"type": "snapshot", **bus.state.snapshot()}


@router.post("/api/confirm")
async def api_confirm() -> dict:
    await hooks.confirm()
    return {"ok": True}


@router.post("/api/cancel")
async def api_cancel() -> dict:
    await hooks.cancel()
    return {"ok": True}


@router.post("/api/stop")
async def api_stop() -> dict:
    await hooks.stop()
    return {"ok": True}


@router.post("/api/reset")
async def api_reset() -> dict:
    await hooks.reset()
    return {"ok": True}


@router.post("/api/start_task")
async def api_start_task(body: dict = Body(...)) -> dict:
    goal = str(body.get("goal", "")).strip()
    if not goal:
        return {"ok": False, "error": "Please say what you would like help with."}
    try:
        await hooks.start_task(goal)
    except Exception as exc:  # e.g. "I'm already helping with something" (safe to show)
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


# ---------- live WebSocket ----------
@router.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket) -> None:
    await ws.accept()
    dead = False

    async def forward(event: dict) -> None:
        nonlocal dead
        if dead:
            return
        try:
            await ws.send_json(event)
        except Exception:
            dead = True  # dropped silently; the receive loop below cleans up

    try:
        await ws.send_json({"type": "snapshot", **bus.state.snapshot()})
        bus.subscribe(forward)
        while True:
            await ws.receive_text()  # we only listen for the disconnect
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        bus.unsubscribe(forward)

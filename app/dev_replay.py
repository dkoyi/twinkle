"""Development helper: replay a scripted fake call onto the real event bus.

    POST /api/dev/replay?scenario=dal      (main demo, asks before pressing play)
    POST /api/dev/replay?scenario=iphone   (safety demo, ends in a red stop)

This lets the dashboard be tested end to end with no phone and no browser agent.
Turn it off in production with DEV_REPLAY=false.
"""
from __future__ import annotations

import asyncio
import os
from urllib.parse import quote

from fastapi import APIRouter, Request, HTTPException

from app.events import bus
from app.dashboard import require_local
from app.sessions import call_lock


async def publish(type, **data):
    return await bus.publish(type, simulated=True, **data)

router = APIRouter()
_running: asyncio.Task | None = None


def _page(title: str, color: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 800">'
        f'<rect width="1280" height="800" fill="#fff"/><rect width="1280" height="76" fill="{color}"/>'
        f'<text x="640" y="430" text-anchor="middle" font-family="Arial" font-size="56" fill="#333">{title}</text></svg>'
    )
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


async def _say(who: str, text: str, pause: float = 0.6) -> None:
    words = text.split()
    await publish("transcript", who=who, text=" ".join(words[: max(2, len(words) // 2)]), final=False)
    await asyncio.sleep(0.4)
    await publish("transcript", who=who, text=text, final=True)
    await asyncio.sleep(pause)


async def _speaking(on: bool) -> None:
    await publish("agent_speaking", speaking=on)


async def _step(task: str, n: int, summary: str, title: str, color: str = "#3a6ea5") -> None:
    await publish("step", task_id=task, n=n, action="click", summary=summary, status="running",
                      point={"x": 0.5, "y": 0.5})
    await asyncio.sleep(0.7)
    await publish("screenshot", task_id=task, n=n, url=_page(title, color))
    await asyncio.sleep(0.4)
    await publish("step", task_id=task, n=n, action="click", summary=summary, status="done")


async def _wait_for_answer(timeout: float = 8.0) -> None:
    waited = 0.0
    while bus.state.pending_approval is not None and waited < timeout:
        await asyncio.sleep(0.2)
        waited += 0.2
    if bus.state.pending_approval is not None:  # nobody answered: approve so a demo never stalls
        await publish("approval_result", task_id="dev", approved=True, by="dashboard")


async def _dal() -> None:
    await publish("reset")
    await publish("call_started", call_sid="dev", **{"from": "4821"})
    await _speaking(True)
    await _say("techtwin", "Hi, I'm TechTwin. What would you like help with on your computer today?")
    await _speaking(False)
    await _say("caller", "My daughter told me about a dal recipe video. Can you play it?")
    await publish("task_started", task_id="dev", goal="Play a dal recipe video")
    await _step("dev", 1, "Opened the video website", "VideoTube")
    await _step("dev", 2, "Typed the name of the video", "Searching: dal recipe")
    await _step("dev", 3, "Found a video that looks right", "Search results")
    await publish("step", task_id="dev", n=4, action="click", summary="Ready to press play", status="running")
    await publish("needs_approval", task_id="dev", step_n=4, question="I found it. Shall I press play?",
                      reason="Playing a video")
    await _wait_for_answer()
    if bus.state.pending_approval is None and bus.history[-1].get("approved") is False:
        await publish("task_finished", task_id="dev", outcome="cancelled", summary="Okay, I didn't press play.",
                          duration_s=20, steps=4)
        return
    await publish("step", task_id="dev", n=4, action="click", summary="Pressed play", status="done")
    await publish("screenshot", task_id="dev", n=5, url=_page("Video playing", "#2b2b2b"))
    await _speaking(True)
    await _say("techtwin", "The video is playing now. Is there anything else?")
    await _speaking(False)
    await publish("task_finished", task_id="dev", outcome="done", summary="The video is playing now.",
                      duration_s=38, steps=4)


async def _iphone() -> None:
    await publish("reset")
    await publish("call_started", call_sid="dev", **{"from": "4821"})
    await _say("caller", "Buy me the new iPhone.")
    await publish("task_started", task_id="dev", goal="Buy the new phone")
    await _step("dev", 1, "Opened a store page", "Pear Phone 17")
    await publish("needs_approval", task_id="dev", step_n=2, question="Shall I add it to the bag?",
                      reason="Adding to a bag")
    await _wait_for_answer()
    await _step("dev", 2, "Added it to the bag", "Your bag")
    await _step("dev", 3, "Went to the checkout", "Payment details")
    await publish("blocked", task_id="dev",
                      reason="This page asks for card details. This part needs you or a family member. "
                             "I won't type payment details.",
                      url="https://store.example/checkout")
    await publish("task_finished", task_id="dev", outcome="blocked", summary="Stopped at the payment page.",
                      duration_s=24, steps=3)


@router.post("/api/dev/replay")
async def replay(request: Request, scenario: str = "dal") -> dict:
    require_local(request)
    if call_lock.locked():
        raise HTTPException(409, "End the real conversation before starting a practice replay.")
    global _running
    if _running and not _running.done():
        _running.cancel()
    async def play():
        async with call_lock:
            await (_iphone() if scenario == "iphone" else _dal())
    _running = asyncio.create_task(play())
    return {"ok": True, "scenario": scenario}


def enabled() -> bool:
    return os.getenv("DEV_REPLAY", "false").lower() != "false"

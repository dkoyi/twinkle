import asyncio

import pytest

from app.events import EventBus


@pytest.fixture
def bus():
    return EventBus()


def run(coro):
    return asyncio.run(coro)


def test_partial_transcript_updates_in_place(bus):
    async def go():
        await bus.publish("transcript", who="techtwin", text="Hi, I'm", final=False)
        await bus.publish("transcript", who="techtwin", text="Hi, I'm TechTwin.", final=True)
        await bus.publish("transcript", who="caller", text="Hello", final=True)
    run(go())
    t = bus.state.transcript
    assert [m["text"] for m in t] == ["Hi, I'm TechTwin.", "Hello"]
    assert t[0]["final"] is True


def test_step_is_updated_not_duplicated(bus):
    async def go():
        await bus.publish("task_started", task_id="t", goal="g")
        await bus.publish("step", task_id="t", n=1, summary="Opening", status="running")
        await bus.publish("step", task_id="t", n=1, summary="Opened", status="done")
    run(go())
    steps = bus.state.steps
    assert len(steps) == 1 and steps[0]["status"] == "done" and steps[0]["summary"] == "Opened"


def test_approval_and_block_lifecycle(bus):
    async def go():
        await bus.publish("needs_approval", task_id="t", step_n=2, question="Shall I?", reason="r")
        assert bus.state.pending_approval["question"] == "Shall I?"
        await bus.publish("approval_result", task_id="t", approved=True, by="voice")
        assert bus.state.pending_approval is None
        await bus.publish("needs_approval", task_id="t", step_n=3, question="Again?", reason="r")
        await bus.publish("blocked", task_id="t", reason="Password", url="x")
        assert bus.state.pending_approval is None and bus.state.blocked["reason"] == "Password"
    run(go())


def test_reset_clears_everything(bus):
    async def go():
        await bus.publish("call_started", call_sid="c", **{"from": "4821"})
        await bus.publish("task_started", task_id="t", goal="g")
        await bus.publish("reset")
    run(go())
    snap = bus.state.snapshot()
    assert snap["call"] is None and snap["task"] is None and snap["steps"] == []


def test_a_broken_listener_does_not_break_others(bus):
    seen = []

    async def bad(ev):
        raise RuntimeError("boom")

    async def good(ev):
        seen.append(ev["type"])

    async def go():
        bus.subscribe(bad)
        bus.subscribe(good)
        await bus.publish("reset")
        await asyncio.sleep(0.05)
    run(go())
    assert seen == ["reset"]

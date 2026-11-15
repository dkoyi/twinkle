import asyncio
import importlib.util
import json
import tempfile
from pathlib import Path

from app.call_log import install
from app.events import EventBus


def load_stats():
    spec = importlib.util.spec_from_file_location("stats", Path(__file__).resolve().parent.parent / "scripts" / "stats.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(coro):
    return asyncio.run(coro)


def test_events_are_logged_one_json_line_each_and_grouped_by_call():
    tmp = tempfile.TemporaryDirectory()
    tmp_path = Path(tmp.name)

    async def go():
        bus = EventBus()
        install(bus, tmp_path)
        await bus.publish("call_started", call_sid="CA1", **{"from": "4821"})
        await bus.publish("task_started", task_id="t1", goal="g")
        await bus.publish("screenshot", task_id="t1", n=1, url="data:image/svg+xml;base64,AAAA")
        await bus.publish("call_ended", call_sid="CA1", duration_s=5)
        await bus.publish("task_started", task_id="t2", goal="later")
        await asyncio.sleep(0.05)

    run(go())
    files = {p.name: [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] for p in tmp_path.rglob("*.jsonl")}
    assert set(files) == {"CA1.jsonl", "t2.jsonl"}
    assert [e["type"] for e in files["CA1.jsonl"]] == ["call_started", "task_started", "screenshot", "call_ended"]
    assert files["CA1.jsonl"][2]["url"] == "(inline image)"
    tmp.cleanup()


def test_stats_counts_tasks_blocks_and_flags_unsafe_actions():
    stats = load_stats()
    ev = lambda type, ts, **kw: {"type": type, "ts": ts, "task_id": "t", **kw}
    good = [ev("task_started", 0), ev("needs_approval", 1), ev("step", 2, status="done"),
            ev("task_finished", 30, outcome="done", duration_s=30.0)]
    blocked = [{**e, "task_id": "b"} for e in [ev("task_started", 0), ev("blocked", 5),
               ev("task_finished", 6, outcome="blocked", duration_s=6.0)]]
    s = stats.summarise(good + blocked)
    assert s["tasks"] == 2 and s["succeeded"] == 1 and s["avg_seconds_when_done"] == 30.0
    assert s["asked_first"] == 1 and s["blocked_by_guard"] == 1 and s["unsafe_actions"] == 0

    bad = blocked + [{"type": "step", "ts": 7, "task_id": "b", "status": "done"}]
    assert stats.summarise(bad)["unsafe_actions"] == 1

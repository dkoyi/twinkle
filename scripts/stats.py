"""Print the pitch numbers from the logs:  python scripts/stats.py [logs-folder]

"Unsafe actions" means an action that ran AFTER the safety guard had already blocked the
task. It must be 0. "Blocked" is how many times the guard stopped something, which is a
good thing to show judges.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(root: Path):
    for f in sorted(root.rglob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass


def summarise(events) -> dict:
    tasks: dict[str, dict] = {}
    for ev in events:
        tid = ev.get("task_id")
        if not tid:
            continue
        t = tasks.setdefault(tid, {"blocked_at": None, "unsafe": 0, "asked": 0, "outcome": None, "dur": None})
        k = ev["type"]
        if k == "blocked":
            t["blocked_at"] = ev["ts"]
        elif k == "needs_approval":
            t["asked"] += 1
        elif k == "step" and ev.get("status") == "done" and t["blocked_at"] and ev["ts"] > t["blocked_at"]:
            t["unsafe"] += 1
        elif k == "task_finished":
            t["outcome"], t["dur"] = ev.get("outcome"), ev.get("duration_s")
    finished = [t for t in tasks.values() if t["outcome"]]
    done = [t for t in finished if t["outcome"] == "done" and t["dur"] is not None]
    return {
        "tasks": len(finished),
        "succeeded": len(done),
        "avg_seconds_when_done": round(sum(t["dur"] for t in done) / len(done), 1) if done else None,
        "asked_first": sum(t["asked"] for t in tasks.values()),
        "blocked_by_guard": sum(1 for t in finished if t["outcome"] == "blocked"),
        "timeouts": sum(1 for t in finished if t["outcome"] == "timeout"),
        "unsafe_actions": sum(t["unsafe"] for t in tasks.values()),
    }


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "logs"
    if not root.exists():
        sys.exit(f"No logs yet in {root}. Run a task first.")
    for k, v in summarise(load(root)).items():
        print(f"{k.replace('_', ' '):<24} {v}")

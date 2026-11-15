"""Call and task logs: one JSON line per event in logs/<date>/<call or task id>.jsonl.

This is where the "measured proof" numbers for the pitch come from (task time, steps,
approvals, blocks). `python scripts/stats.py` summarises them.

Turn on in the app with `install()` (main.py does this); turn off with LOG_EVENTS=false.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app.events import EventBus, bus as default_bus

LOG_ROOT = Path(__file__).resolve().parent.parent / "logs"


class CallLog:
    def __init__(self, root: Path = LOG_ROOT) -> None:
        self.root = root
        self._call_id: str | None = None

    def _file(self, ev: dict) -> Path:
        t = ev["type"]
        if t == "call_started":
            self._call_id = str(ev.get("call_sid") or f"call-{int(ev['ts'])}")
        key = self._call_id or ev.get("task_id") or "session"
        day = time.strftime("%Y-%m-%d", time.localtime(ev["ts"]))
        folder = self.root / day
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{key}.jsonl"

    async def __call__(self, ev: dict) -> None:
        row = dict(ev)
        if str(row.get("url", "")).startswith("data:"):
            row["url"] = "(inline image)"      # keep dev screenshots out of the logs
        with open(self._file(ev), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if ev["type"] == "call_ended":
            self._call_id = None


def enabled() -> bool:
    return os.getenv("LOG_EVENTS", "true").lower() != "false"


def install(bus: EventBus = default_bus, root: Path = LOG_ROOT) -> CallLog:
    log = CallLog(root)
    bus.subscribe(log)
    return log

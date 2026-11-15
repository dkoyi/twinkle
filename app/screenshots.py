"""Latest browser screenshot, kept in memory.

The task runner writes it; the dashboard serves it. They never import each other,
only this tiny module (the one-rule from docs/BACKEND_HANDOFF.md).
"""
from __future__ import annotations


class _Latest:
    jpeg: bytes | None = None
    n: int = 0


def set_latest(jpeg: bytes) -> str:
    """Store the newest screenshot; returns the URL to put in the `screenshot` event."""
    _Latest.jpeg = jpeg
    _Latest.n += 1
    return f"/api/screenshot?v={_Latest.n}"


def get_latest() -> bytes | None:
    return _Latest.jpeg


def clear() -> None:
    _Latest.jpeg = None

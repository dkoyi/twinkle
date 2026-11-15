"""All configuration comes from environment variables (.env). Read fresh on every call
so tests can change them. Names match .env.example."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _list(name: str, default: str = "") -> list[str]:
    return [p.strip().lower() for p in os.getenv(name, default).split(",") if p.strip()]


@dataclass(frozen=True)
class Settings:
    allowed_domains: list[str]
    ask_first_extra: list[str]
    max_task_seconds: int
    max_task_steps: int
    demo_mode: bool
    headless: bool
    fake_media: bool
    start_url: str
    viewport_w: int
    viewport_h: int
    computer_use_model: str
    describe_model: str
    gemini_api_key: str
    approval_timeout_s: int


def get_settings() -> Settings:
    return Settings(
        allowed_domains=_list("ALLOWED_DOMAINS", "youtube.com,google.com,zoom.us,meet.google.com,cvs.com,apple.com"),
        # Extra words that need a spoken yes. "play" so TechTwin asks "Shall I press play?" in the demo.
        ask_first_extra=_list("ASK_FIRST_EXTRA", "play"),
        max_task_seconds=_int("MAX_TASK_SECONDS", 120),
        max_task_steps=_int("MAX_TASK_STEPS", 25),
        demo_mode=_bool("DEMO_MODE", True),
        headless=_bool("HEADLESS", False),  # the real demo browser is always visible
        fake_media=_bool("FAKE_MEDIA", True),  # auto-allow a fake camera/mic so meeting pages don't stall
        start_url=os.getenv("START_URL", "http://localhost:8000/static/start.html"),
        viewport_w=_int("VIEWPORT_W", 1280),
        viewport_h=_int("VIEWPORT_H", 800),
        computer_use_model=os.getenv("COMPUTER_USE_MODEL", "gemini-2.5-computer-use-preview-10-2025"),
        describe_model=os.getenv("DESCRIBE_MODEL", "gemini-2.5-flash"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        approval_timeout_s=_int("APPROVAL_TIMEOUT_S", 60),
    )

"""TechTwin server.  Run:  uvicorn app.main:app --reload --port 8000

Teammates: add your routers here (include_router) and start/stop long-lived things
(Playwright browser, etc.) in `lifespan`.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app import call_log, dashboard, dev_replay  # noqa: E402  (after load_dotenv so .env is visible)

STATIC = Path(__file__).resolve().parent.parent / "static"


def _wire_runner() -> None:
    """Point the dashboard buttons at the real task runner."""
    from functools import partial

    from app.task_runner import runner

    dashboard.hooks.confirm = partial(runner.confirm, by="dashboard")
    dashboard.hooks.cancel = partial(runner.cancel, by="dashboard")
    dashboard.hooks.stop = runner.stop
    dashboard.hooks.reset = runner.reset
    dashboard.hooks.start_task = runner.start


@asynccontextmanager
async def lifespan(app: FastAPI):
    autostart = os.getenv("BROWSER_AUTOSTART", "true").lower() != "false"
    if autostart:
        from app.events import bus
        from app.task_runner import browser

        _wire_runner()
        if call_log.enabled():
            call_log.install()
        try:
            await browser.start()  # one visible Chromium for the whole server lifetime
        except Exception as exc:
            print(f"[startup] Could not open the browser: {exc!r}\n"
                  "          Run:  python -m playwright install chromium")
            await bus.publish("error", where="browser", message=str(exc))
    yield
    if autostart:
        from app.task_runner import browser

        await browser.stop()


app = FastAPI(title="TechTwin", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.include_router(dashboard.router)
if dev_replay.enabled():
    app.include_router(dev_replay.router)


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return (
        "<h1>TechTwin is running</h1>"
        '<p><a href="/dashboard">Open the dashboard</a> &middot; '
        '<a href="/static/dashboard.html?demo=dal">Practice run (no server needed)</a></p>'
    )


@app.get("/dashboard")
async def dashboard_page() -> FileResponse:
    return FileResponse(STATIC / "dashboard.html")


@app.get("/family")
async def family_page():
    page = STATIC / "family.html"
    return FileResponse(page) if page.exists() else RedirectResponse("/dashboard")

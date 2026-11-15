"""TechTwin server.  Run:  uvicorn app.main:app --reload --port 8000

Teammates: add your routers here (include_router) and start/stop long-lived things
(Playwright browser, etc.) in `lifespan`.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app import dashboard, dev_replay  # noqa: E402  (after load_dotenv so .env is visible)

STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: launch Playwright here (once), connect anything long-lived
    yield
    # shutdown: close the browser here


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

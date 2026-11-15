"""Run with: uvicorn app.main:app --reload --port 8000."""
import asyncio
import logging
import anyio
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
from app.events import bus
from app.twilio_stream import router
from app.browser_voice import router as browser_voice_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = FastAPI(title="TechTwin")
app.include_router(router)
app.include_router(browser_voice_router)
VOICE_DEMO = Path(__file__).resolve().parent.parent / "voice_demo"
app.mount("/voice-demo", StaticFiles(directory=VOICE_DEMO), name="voice-demo")
STATIC = Path(__file__).resolve().parent.parent / "static"
if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
async def root():
    return {"message": "TechTwin is running", "voice_webhook": "/voice", "browser_voice": "/talk"}


@app.get("/talk")
async def talk():
    return FileResponse(VOICE_DEMO / "index.html")


def snapshot():
    state = {"call": None, "task": None, "steps": [], "transcript": [],
             "pending_approval": None, "blocked": None}
    for event in list(bus.history):
        kind = event["type"]
        if kind == "reset":
            state = {"call": None, "task": None, "steps": [], "transcript": [],
                     "pending_approval": None, "blocked": None}
        elif kind in {"call_started", "call_ended"}:
            state["call"] = event
        elif kind == "transcript":
            rows = state["transcript"]
            if rows and rows[-1]["who"] == event["who"] and not rows[-1]["final"]:
                rows[-1] = event
            else:
                rows.append(event)
        elif kind in {"task_started", "task_finished"}:
            state["task"] = event
            state["pending_approval"] = None
        elif kind == "step":
            rows = state["steps"]
            old = next((i for i, row in enumerate(rows) if (row["task_id"], row["n"]) ==
                        (event["task_id"], event["n"])), None)
            if old is None:
                rows.append(event)
            else:
                rows[old] = event
        elif kind == "needs_approval":
            state["pending_approval"] = event
        elif kind == "approval_result":
            state["pending_approval"] = None
        elif kind == "blocked":
            state["blocked"] = event
    return state


@app.get("/api/state")
async def state():
    return snapshot()


@app.get("/dashboard")
async def dashboard():
    path = STATIC / "dashboard.html"
    if path.exists():
        return FileResponse(path)
    return {"message": "The phone backend is ready. Shrey's dashboard will appear here when added."}


@app.websocket("/ws/dashboard")
async def dashboard_events(ws: WebSocket):
    await ws.accept()
    queue = asyncio.Queue(maxsize=100)
    async def forward(event):
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(event)
    unsubscribe = bus.subscribe(forward)
    async def send():
        while True:
            await ws.send_json(await queue.get())
    async def receive():
        while True:
            await ws.receive_text()
    workers = []
    try:
        await ws.send_json({"type": "snapshot", **snapshot()})
        workers = [asyncio.create_task(send()), asyncio.create_task(receive())]
        done, _ = await asyncio.wait(workers, return_when=asyncio.FIRST_COMPLETED)
        for worker in done:
            worker.result()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        unsubscribe()
        with anyio.CancelScope(shield=True):
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

"""Run with: uvicorn app.main:app --reload --port 8000."""
import asyncio
import logging
from contextlib import asynccontextmanager
import time
import anyio
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
from app.events import bus
from app.twilio_stream import router
from app.browser_voice import router as browser_voice_router
from app.dashboard import router as dashboard_router, state, clear_screenshot
from app.integration import bridge
from app.call_log import CallLog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
@asynccontextmanager
async def lifespan(app):
    state.reset()
    clear_screenshot()
    call_log = CallLog(Path(__file__).resolve().parent.parent / "logs")
    unsubscribers = [bus.subscribe(call_log.on_event),
                    bus.subscribe(bridge.on_event)]
    try:
        yield
    finally:
        await bridge.close()
        for unsubscribe in unsubscribers:
            unsubscribe()


app = FastAPI(title="TechTwin", lifespan=lifespan)
app.include_router(router)
app.include_router(browser_voice_router)
app.include_router(dashboard_router)
from app import dev_replay
if dev_replay.enabled():
    app.include_router(dev_replay.router)
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
    return state.snapshot()


@app.get("/dashboard")
async def dashboard():
    path = STATIC / "dashboard.html"
    if path.exists():
        return FileResponse(path)
    return {"message": "The phone backend is ready. Shrey's dashboard will appear here when added."}


@app.get("/family")
async def family():
    path = STATIC / "family.html"
    return FileResponse(path) if path.exists() else RedirectResponse("/dashboard")


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
        await ws.send_json({"type": "snapshot", "ts": time.time(), **snapshot()})
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

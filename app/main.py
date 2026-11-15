"""Run with: uvicorn app.main:app --reload --port 8000."""
import asyncio
import logging
import os
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
from app.call_log import CallLog, enabled as logs_enabled

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
@asynccontextmanager
async def lifespan(app):
    state.reset()
    clear_screenshot()
    call_log = CallLog(Path(__file__).resolve().parent.parent / "logs")
    unsubscribers = [bus.subscribe(bridge.on_event)]
    if logs_enabled():
        unsubscribers.append(bus.subscribe(call_log.on_event))
    browser = None
    startup_task = None
    try:
        if os.getenv('BROWSER_AUTOSTART', 'true').lower() != 'false':
            from app.task_runner import browser, runner
            async def start_helper():
                try:
                    await browser.start()
                    bridge.attach(runner)
                    await runner._show('preview', 0)
                    # Read the latest streamed frame, including after a task
                    # ends. These reads never trigger browser screenshots.
                    while True:
                        await asyncio.sleep(2)
                        try:
                            await runner._show(runner.task_id or 'preview', runner._steps)
                        except Exception:
                            logging.getLogger(__name__).debug('Waiting for the next browser frame')
                except Exception:
                    logging.getLogger(__name__).exception('Browser startup failed')
                    await bus.publish('error', where='browser', message='The laptop helper could not open. Restart the server after installing Chromium.')
            # The clean start page is served by this app, so start accepting HTTP
            # before the helper navigates there. Awaiting it here deadlocks startup.
            startup_task = asyncio.create_task(start_helper())
        yield
    finally:
        if startup_task:
            startup_task.cancel()
            await asyncio.gather(startup_task, return_exceptions=True)
        await bridge.close()
        if browser:
            await browser.stop()
            bridge.attach(None)
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


NO_STORE = {'Cache-Control': 'no-store'}


@app.get("/")
@app.get("/talk")
async def talk():
    """The phone page: an iPhone call to Twinkle. static/voice.js carries the real call."""
    return FileResponse(STATIC / "phone.html", headers=NO_STORE)


@app.get("/classic")
async def classic_talk():
    """The earlier all-in-one call page (phone, transcript and laptop view together)."""
    return FileResponse(VOICE_DEMO / "index.html", headers=NO_STORE)


@app.get("/help")
async def help_page():
    return FileResponse(STATIC / "help.html", headers=NO_STORE)


@app.get("/api/health")
async def health():
    return {"message": "TechTwin is running", "voice_webhook": "/voice", "browser_voice": "/talk"}


def snapshot():
    return state.snapshot()


@app.get("/dashboard")
async def dashboard():
    path = STATIC / "dashboard.html"
    if path.exists():
        return FileResponse(path, headers={'Cache-Control': 'no-store'})
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

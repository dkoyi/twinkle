"""Local browser microphone transport: PCM16 16k in, PCM16 24k out."""
import asyncio
import base64
import json
import logging
import time
from urllib.parse import urlsplit
from uuid import uuid4

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException
from app.config import Settings
from app.events import bus
from app.sessions import call_lock
from app.voice_brain import VoiceBrain
from app.integration import bridge

router = APIRouter()
log = logging.getLogger(__name__)
browser_calls = {}


@router.get('/api/voice/status')
async def voice_status():
    media = None
    browser = getattr(bridge.runner, 'browser', None)
    if browser is not None and browser.started:
        try:
            media = await asyncio.wait_for(browser.media_state(), 1)
        except Exception:
            pass
    return {'voice_ready': bool(Settings.from_env().api_key),
            'helper_connected': bool(bridge.available and (browser is None or browser.started)),
            'screenshot_url': bus.state.screenshot_url, 'media': media,
            'active_call': next(({'call_sid': sid, 'started_at': call['started_at']}
                                 for sid, call in browser_calls.items()), None)}


@router.post('/api/voice/end')
async def end_browser_call(request: Request):
    if not local_origin(request):
        raise HTTPException(403, 'Use this control from the local TechTwin website.')
    payload = await request.json()
    call = browser_calls.get(payload.get('call_sid'))
    if call is not None:
        call['end'].set()
        try:
            await asyncio.wait_for(asyncio.shield(call['closed']), 3)
        except asyncio.TimeoutError:
            raise HTTPException(503, 'The call is still ending. Please try again.')
    return {'ok': True}


def local_origin(ws):
    # The ngrok phone webhook stays available, but computer-control voice access
    # is local-only until the team adds user authentication for remote browsers.
    host = urlsplit('http://' + ws.headers.get('host', '')).hostname
    origin = urlsplit(ws.headers.get('origin', ''))
    return (host in {'localhost', '127.0.0.1', '[::1]', '::1'}
            and origin.scheme in {'http', 'https'}
            and origin.netloc == ws.headers.get('host')
            and not ws.headers.get('x-forwarded-host'))


class BrowserPlayback:
    def __init__(self, ws, call_sid):
        self.ws, self.call_sid = ws, call_sid
        self.queue = asyncio.Queue(maxsize=512)
        self.generation = 0
        self.lock = asyncio.Lock()
        self.speaking = False
        self.last_mark = None
        self.mark_count = 0

    def enqueue(self, event, *, audio=False):
        self.queue.put_nowait((self.generation if audio else None, event))

    def pcm(self, data):
        self.enqueue({'type': 'audio', 'data': base64.b64encode(data).decode(),
                      'rate': 24000, 'generation': self.generation}, audio=True)

    def finish(self):
        self.mark_count += 1
        self.last_mark = f'{self.generation}:{self.mark_count}'
        self.enqueue({'type': 'audio_end', 'mark': self.last_mark,
                      'generation': self.generation}, audio=True)

    async def status(self, value):
        if self.speaking != value:
            self.speaking = value
            await bus.publish('agent_speaking', call_sid=self.call_sid, speaking=value)

    async def clear(self):
        async with self.lock:
            self.generation += 1
            self.last_mark = None
            await self.ws.send_json({'type': 'clear', 'generation': self.generation})
        await self.status(False)

    async def acknowledge(self, mark):
        if mark == self.last_mark:
            await self.status(False)

    async def run(self):
        while True:
            generation, event = await self.queue.get()
            async with self.lock:
                if generation is not None and generation != self.generation:
                    continue
                await self.ws.send_json(event)
            if event['type'] == 'audio':
                await self.status(True)


async def receive_audio(ws, incoming, playback, call_sid):
    while True:
        message = await asyncio.wait_for(ws.receive(), 45)
        if message['type'] == 'websocket.disconnect':
            return
        data = message.get('bytes')
        if data is not None:
            if not 2 <= len(data) <= 8192 or len(data) % 2:
                raise ValueError('Invalid microphone audio frame')
            incoming.put_nowait(data)
        else:
            command = json.loads(message.get('text', '{}'))
            if command.get('type') == 'end':
                return
            if command.get('type') == 'played':
                await playback.acknowledge(command.get('mark'))
            elif command.get('type') == 'stop':
                await playback.clear()
                await bus.publish('voice_command', request_id=None, name='stop_task',
                                  arguments={}, call_sid=call_sid)


@router.websocket('/ws/voice')
async def browser_voice(ws: WebSocket):
    if not local_origin(ws):
        await ws.close(code=1008)
        return
    await ws.accept()
    settings = Settings.from_env()
    if not settings.api_key:
        await ws.send_json({'type': 'error', 'message': 'Add GEMINI_API_KEY to .env and restart the server.'})
        await ws.close(code=1008)
        return
    if call_lock.locked():
        await ws.send_json({'type': 'error', 'message': 'Another conversation is open. End it before starting here.'})
        await ws.close(code=1013)
        return
    async with call_lock:
        call_sid = 'browser-' + uuid4().hex
        started = time.monotonic()
        call = {'end': asyncio.Event(), 'closed': asyncio.get_running_loop().create_future(),
                'started_at': time.time()}
        browser_calls[call_sid] = call
        playback = BrowserPlayback(ws, call_sid)
        incoming = asyncio.Queue(maxsize=250)
        async def forward(event):
            if event.get('call_sid', call_sid) == call_sid and event['type'] in {
                    'voice_ready', 'transcript', 'agent_speaking', 'error', 'needs_approval',
                    'blocked', 'task_started', 'task_finished', 'step', 'screenshot', 'approval_result'}:
                playback.enqueue(event)
        unsubscribe = bus.subscribe(forward)
        workers = []
        try:
            await bus.publish('call_started', call_sid=call_sid,
                              **{'from': '', 'transport': 'browser',
                                 'agent_id': 'agent-1', 'agent_name': 'Agent 1'})
            brain = VoiceBrain(settings, bus, playback, call_sid, decode_audio=lambda data: data)
            workers = [asyncio.create_task(call['end'].wait()),
                       asyncio.create_task(playback.run()),
                       asyncio.create_task(receive_audio(ws, incoming, playback, call_sid)),
                       asyncio.create_task(brain.run(incoming))]
            async with asyncio.timeout(600):
                done, _ = await asyncio.wait(workers, return_when=asyncio.FIRST_COMPLETED)
                for worker in done:
                    worker.result()
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception as error:
            # Don't send provider exceptions, which can contain account details, to browsers.
            log.error('Browser voice failed: %s', type(error).__name__)
            message = 'The voice connection ended. Check your Gemini key and quota, then try again.'
            if isinstance(error, TimeoutError):
                message = 'The conversation timed out. You can start again.'
            try:
                async with playback.lock:
                    await ws.send_json({'type': 'error', 'message': message})
            except (RuntimeError, WebSocketDisconnect):
                pass
            await bus.publish('error', where='browser_voice', message=message, call_sid=call_sid)
        finally:
            unsubscribe()
            with anyio.CancelScope(shield=True):
                for worker in workers:
                    worker.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
                # Wait for cancellation before releasing ownership to another
                # call. A queued stop must never cancel the next caller's task.
                await bus.command('stop_task', call_sid=call_sid, timeout=2)
                await playback.status(False)
                await bus.publish('call_ended', call_sid=call_sid, duration_s=round(time.monotonic() - started, 2))
                try:
                    await ws.close()
                except (RuntimeError, WebSocketDisconnect):
                    pass
                browser_calls.pop(call_sid, None)
                if not call['closed'].done():
                    call['closed'].set_result(True)

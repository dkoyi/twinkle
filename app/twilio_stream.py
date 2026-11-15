"""Authenticated Twilio voice webhook and bidirectional Media Stream."""
import asyncio
import logging
import time
import anyio
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse, Connect
from app.config import Settings
from app.events import bus
from app.playback import Playback
from app.voice_brain import VoiceBrain
from app.sessions import call_lock as _call_lock

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/voice")
async def voice(request: Request):
    settings = Settings.from_env()
    try:
        settings.check()
    except ValueError as error:
        raise HTTPException(503, str(error)) from error
    form = await request.form()
    if settings.validate_signatures and not RequestValidator(settings.auth_token).validate(
            settings.public_base_url + "/voice", form, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, "Invalid Twilio signature")
    response = VoiceResponse()
    response.say("Hi, this is TechTwin.")
    connect = Connect()
    stream = connect.stream(url="wss://" + urlsplit(settings.public_base_url).netloc + "/media")
    stream.parameter(name="caller_last4", value=str(form.get("From", ""))[-4:])
    response.append(connect)
    return Response(str(response), media_type="application/xml")


async def echo(incoming, playback):
    while True:
        playback.frame(await incoming.get())


@router.websocket("/media")
async def media(ws: WebSocket):
    settings = Settings.from_env()
    try:
        settings.check()
    except ValueError:
        await ws.close(code=1011)
        return
    # Validate against the configured public origin, never untrusted proxy headers.
    # Accommodate Twilio's WSS handshake URL/trailing-slash normalization.
    media_url = settings.public_base_url + "/media"
    handshake_urls = [media_url, media_url + "/", media_url.replace("https://", "wss://", 1),
                      media_url.replace("https://", "wss://", 1) + "/"]
    if settings.validate_signatures and not any(RequestValidator(settings.auth_token).validate(
            url, {}, ws.headers.get("X-Twilio-Signature", "")) for url in handshake_urls):
        await ws.close(code=1008)
        return
    # The shared browser belongs to one call at a time.
    if _call_lock.locked():
        await ws.close(code=1013)
        return
    async with _call_lock:
        await ws.accept()
        call_sid = None
        started = time.monotonic()
        workers = []
        playback = None
        try:
            incoming = asyncio.Queue(maxsize=250)
            # A broken or idle socket must not reserve the demo browser indefinitely.
            async with asyncio.timeout(600):
                while True:
                    event = await asyncio.wait_for(ws.receive_json(), timeout=30)
                    kind = event.get("event")
                    log.debug("Twilio event: %s", kind)  # Never log audio payloads.
                    if kind == "start":
                        if call_sid:
                            raise ValueError("Duplicate stream start")
                        start = event["start"]
                        if settings.account_sid and start.get("accountSid") != settings.account_sid:
                            raise ValueError("Unexpected Twilio account")
                        fmt = start.get("mediaFormat", {})
                        if fmt != {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1}:
                            raise ValueError("Unsupported phone audio format")
                        call_sid, stream_sid = start["callSid"], start["streamSid"]
                        started = time.monotonic()
                        playback = Playback(ws, stream_sid, bus, call_sid)
                        await bus.publish("call_started", call_sid=call_sid,
                                          **{"from": start.get("customParameters", {}).get("caller_last4", "")[-4:]})
                        workers.append(asyncio.create_task(playback.run()))
                        if settings.voice_mode == "echo":
                            workers.append(asyncio.create_task(echo(incoming, playback)))
                        else:
                            brain = VoiceBrain(settings, bus, playback, call_sid)
                            workers.append(asyncio.create_task(brain.run(incoming)))
                        # Close the socket on a failed Gemini connection, waking receive_json.
                        for worker in workers:
                            worker.add_done_callback(lambda task: asyncio.create_task(close_failed(ws, task)))
                    elif kind == "media" and call_sid:
                        if event.get("media", {}).get("track", "inbound") == "inbound":
                            incoming.put_nowait(event["media"]["payload"])
                    elif kind == "mark" and playback:
                        await playback.acknowledge(event.get("mark", {}).get("name"))
                    elif kind == "stop":
                        break
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            log.exception("Phone stream failed")
            await bus.publish("error", where="phone", message="The phone connection stopped. Please call again.",
                              call_sid=call_sid)
        finally:
            with anyio.CancelScope(shield=True):
                for worker in workers:
                    worker.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
                if call_sid:
                    await bus.publish("voice_command", request_id=None, name="stop_task", arguments={}, call_sid=call_sid)
                    if playback:
                        await playback.status(False)
                    await bus.publish("call_ended", call_sid=call_sid, duration_s=round(time.monotonic() - started, 2))
                try:
                    await ws.close()
                except RuntimeError:
                    pass


async def close_failed(ws, task):
    if not task.cancelled() and task.exception():
        log.error("Voice worker failed: %s", type(task.exception()).__name__)
        await bus.publish("error", where="voice", message="The voice helper disconnected. Please call again.")
        try:
            await ws.close(code=1011)
        except RuntimeError:
            pass

"""Paced Twilio playback with atomic interruption and playback acknowledgments."""
import asyncio
import itertools
from app.audio import gemini_out_to_twilio


class Playback:
    def __init__(self, websocket, stream_sid, events, call_sid):
        self.ws, self.sid, self.events, self.call_sid = websocket, stream_sid, events, call_sid
        self.queue = asyncio.Queue(maxsize=1500)  # At most 30 seconds of queued speech.
        self.buffer = bytearray()
        self.lock = asyncio.Lock()
        self.generation = 0
        self.speaking = False
        self.last_mark = None
        self.marks = itertools.count()

    def pcm(self, data: bytes):
        self.buffer.extend(data)
        while len(self.buffer) >= 960:
            block = bytes(self.buffer[:960])
            del self.buffer[:960]
            self.frame(gemini_out_to_twilio(block)[0])

    def frame(self, payload):
        self.queue.put_nowait((self.generation, "media", payload))

    def finish(self):
        if self.buffer:
            for frame in gemini_out_to_twilio(bytes(self.buffer)):
                self.frame(frame)
            self.buffer.clear()
        mark = f"{self.generation}:{next(self.marks)}"
        self.last_mark = mark
        self.queue.put_nowait((self.generation, "mark", mark))

    async def status(self, speaking):
        if self.speaking != speaking:
            self.speaking = speaking
            await self.events.publish("agent_speaking", speaking=speaking, call_sid=self.call_sid)

    async def acknowledge(self, mark):
        if mark == self.last_mark and self.queue.empty():
            await self.status(False)

    async def clear(self):
        async with self.lock:
            self.generation += 1
            self.last_mark = None
            self.buffer.clear()
            while not self.queue.empty():
                self.queue.get_nowait()
            await self.ws.send_json({"event": "clear", "streamSid": self.sid})
            await self.status(False)

    async def run(self):
        while True:
            generation, kind, payload = await self.queue.get()
            async with self.lock:
                if generation != self.generation:
                    continue
                if kind == "media":
                    await self.status(True)
                await self.ws.send_json({"event": kind, "streamSid": self.sid,
                                         kind: {"payload" if kind == "media" else "name": payload}})
            if kind == "media":
                await asyncio.sleep(.020)

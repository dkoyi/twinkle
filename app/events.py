"""Shared, ordered event interface. Listeners must return promptly."""
import asyncio
import logging
import time
from collections import deque
from typing import Any, Awaitable, Callable
from uuid import uuid4

Listener = Callable[[dict], Awaitable[None]]
log = logging.getLogger(__name__)


class EventBus:
    def __init__(self, history_limit: int = 500) -> None:
        self._listeners: list[Listener] = []
        self.history: deque[dict] = deque(maxlen=history_limit)
        self._pending: dict[str, asyncio.Future] = {}

    def subscribe(self, fn: Listener) -> Callable[[], None]:
        self._listeners.append(fn)
        def unsubscribe():
            if fn in self._listeners:
                self._listeners.remove(fn)
        return unsubscribe

    async def publish(self, type: str, **data: Any) -> None:
        event = {**data, "type": type, "ts": time.time()}
        self.history.append(event)
        log.info("[event] %s", event)
        if type == "voice_command_result":
            future = self._pending.get(data.get("request_id"))
            if future is not None and not future.done():
                future.set_result(data.get("result", {}))
        for fn in list(self._listeners):
            try:
                await fn(event)
            except Exception:
                log.exception("Event listener failed for %s", type)

    async def command(self, name: str, *, call_sid: str, timeout: float = 2, **arguments) -> dict:
        request_id = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self.publish("voice_command", request_id=request_id, name=name,
                               arguments=arguments, call_sid=call_sid)
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            return {"ok": False, "message": "The computer helper is not connected yet. Please try again shortly."}
        finally:
            self._pending.pop(request_id, None)


bus = EventBus()

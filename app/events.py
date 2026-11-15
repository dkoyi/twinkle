"""Shared, ordered event interface. Listeners must return promptly."""
import asyncio
import logging
import time
from collections import deque
from copy import deepcopy
from typing import Any, Awaitable, Callable
from uuid import uuid4

Listener = Callable[[dict], Awaitable[None]]
log = logging.getLogger(__name__)


class State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = {'call': None, 'task': None, 'steps': [], 'transcript': [],
                      'pending_approval': None, 'blocked': None,
                      'speaking': False, 'screenshot_url': None, 'page_url': ''}

    def __getattr__(self, name):
        if name in self.state:
            return self.state[name]
        raise AttributeError(name)

    def snapshot(self):
        return deepcopy(self.state)

    async def on_event(self, event):
        self.apply(event)

    def apply(self, event):
        kind, state = event['type'], self.state
        if kind == 'reset':
            self.reset()
        elif kind == 'call_started':
            state['call'] = event
        elif kind == 'call_ended':
            state['call'] = None
            state['speaking'] = False
        elif kind == 'agent_speaking':
            state['speaking'] = bool(event['speaking'])
        elif kind == 'transcript':
            rows = state['transcript']
            partial = next((i for i in range(len(rows)-1, -1, -1)
                            if rows[i]['who'] == event['who'] and not rows[i]['final']), None)
            if partial is None:
                rows.append(event)
            else:
                rows[partial] = event
            del rows[:-300]
        elif kind == 'task_started':
            state.update(task={**event, 'id': event['task_id'], 'finished': False},
                         steps=[], pending_approval=None, blocked=None, screenshot_url=None, page_url='')
        elif kind == 'task_finished':
            started = (state['task'] or {}).get('ts', event['ts'])
            state['task'] = {**(state['task'] or {}), **event, 'finished': True,
                             'ts': started, 'finished_ts': event['ts']}
            state['pending_approval'] = None
        elif kind == 'step':
            rows = state['steps']
            old = next((i for i, row in enumerate(rows) if (row['task_id'], row['n']) ==
                        (event['task_id'], event['n'])), None)
            if old is None:
                rows.append(event)
            else:
                rows[old] = event
        elif kind == 'needs_approval':
            state['pending_approval'] = event
        elif kind == 'approval_result':
            state['pending_approval'] = None
        elif kind == 'blocked':
            state['blocked'] = event
            state['pending_approval'] = None
        elif kind == 'screenshot':
            # Only serve our own screenshot route, not arbitrary remote image URLs.
            url = event.get('url', '')
            if url.startswith('/api/screenshot?') or url == '/api/screenshot':
                state['screenshot_url'] = url
            state['page_url'] = event.get('page_url', '')



class EventBus:
    def __init__(self, history_limit: int = 500) -> None:
        self._listeners: list[Listener] = []
        self.state = State()
        self.history: deque[dict] = deque(maxlen=history_limit)
        self._pending: dict[str, asyncio.Future] = {}

    def subscribe(self, fn: Listener) -> Callable[[], None]:
        if fn not in self._listeners:
            self._listeners.append(fn)
        def unsubscribe():
            if fn in self._listeners:
                self._listeners.remove(fn)
        return unsubscribe

    def unsubscribe(self, fn: Listener) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    async def publish(self, type: str, **data: Any) -> dict:
        event = {**data, "type": type, "ts": time.time()}
        self.state.apply(event)
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

        return event

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

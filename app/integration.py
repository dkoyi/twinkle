"""Bridge shared commands to the browser runner without coupling voice to it.

Dhaush's startup code calls attach_runner(runner) after creating the runner.
Runner methods follow docs/BACKEND_HANDOFF.md. No simulated browser successes.
"""
import asyncio
import inspect
import logging
from app.events import bus

log = logging.getLogger(__name__)


class RunnerBridge:
    def __init__(self, events=bus):
        self.events = events
        self.runner = None
        self.hooks = None
        self.workers = set()
        self.epoch = 0

    def attach(self, runner):
        self.runner = runner

    @property
    def available(self):
        return self.runner is not None or (self.hooks is not None and any(
            callable(getattr(self.hooks, name, None))
            for name in ('start_task', 'confirm', 'cancel', 'stop', 'reset', 'describe')))

    async def execute(self, name, arguments=None, by='voice'):
        if not self.available:
            return {'ok': False, 'message': 'The computer helper is not connected yet.'}
        arguments = arguments or {}
        method = {'start_task': 'start', 'confirm_action': 'confirm', 'cancel_action': 'cancel',
                  'describe_screen': 'describe', 'stop_task': 'stop', 'reset': 'reset'}.get(name)
        if method is None:
            return {'ok': False, 'message': 'Unknown computer command.'}
        target = self.runner if self.runner is not None else self.hooks
        callback = getattr(target, 'start_task' if target is self.hooks and method == 'start' else method, None)
        if not callable(callback):
            return {'ok': False, 'message': 'That computer command is not connected yet.'}
        try:
            if method == 'start':
                result = await callback(arguments['goal'])
                return {'ok': True, 'task_id': result, 'message': 'Started'}
            # A runner command must return promptly; its browser loop runs separately.
            kwargs = {'by': by} if 'by' in inspect.signature(callback).parameters else {}
            result = await callback(**kwargs)
            return {'ok': True, **({'description': result} if method == 'describe' else {})}
        except Exception:
            log.exception('Browser command failed: %s', name)
            return {'ok': False, 'message': 'The computer could not do that step. Please try again.'}

    async def on_event(self, event):
        if event['type'] != 'voice_command':
            return
        name = event['name']
        if name in {'stop_task', 'reset'}:
            self.epoch += 1
            # Cancel older commands before issuing stop; never run a queued start afterward.
            for worker in list(self.workers):
                worker.cancel()
        epoch = self.epoch
        async def command():
            if epoch != self.epoch:
                return
            result = await self.execute(name, event.get('arguments'),
                                        by='dashboard' if event.get('call_sid') == 'dashboard' else 'voice')
            if event.get('request_id'):
                await self.events.publish('voice_command_result', request_id=event['request_id'], result=result)
        task = asyncio.create_task(command())
        self.workers.add(task)
        task.add_done_callback(self.workers.discard)

    async def screenshot(self):
        if self.runner is None:
            return None
        # An explicit byte getter avoids reading arbitrary file paths from events.
        getter = getattr(self.runner, 'get_screenshot', None)
        image = getter() if getter else getattr(self.runner, 'latest_screenshot', None)
        if inspect.isawaitable(image):
            image = await image
        return image if isinstance(image, bytes) else None

    async def close(self):
        for worker in list(self.workers):
            worker.cancel()
        await asyncio.gather(*list(self.workers), return_exceptions=True)
        if self.available:
            await self.execute('stop_task')


bridge = RunnerBridge()


def attach_runner(runner):
    """Register the real TaskRunner once, after it has initialized its browser."""
    bridge.attach(runner)

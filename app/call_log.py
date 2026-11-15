"""Append demo events to per-call JSONL files, excluding voice audio and secrets."""
import json
import logging
import re
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)
LOGGED = {'call_started', 'call_ended', 'transcript', 'task_started', 'task_finished',
          'step', 'needs_approval', 'approval_result', 'blocked', 'error', 'reset',
          'voice_command', 'voice_command_result', 'screenshot'}


class CallLog:
    def __init__(self, root=Path('logs')):
        self.root = Path(root)
        self.active_call = None

    async def on_event(self, event):
        kind = event['type']
        if kind not in LOGGED or event.get('simulated'):
            return
        if kind == 'call_started':
            self.active_call = event['call_sid']
        identifier = event.get('call_sid') or self.active_call or event.get('task_id') or 'demo'
        identifier = re.sub(r'[^a-zA-Z0-9_-]', '_', str(identifier))[:100]
        date = datetime.fromtimestamp(event['ts']).strftime('%Y-%m-%d')
        # Sequential writes preserve event order; demo volume is a few short lines/sec.
        # The directory is ignored by git. Never persist media frames or API keys.
        try:
            directory = self.root / date
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / (identifier + '.jsonl')).open('a') as file:
                row = dict(event)
                if str(row.get('url', '')).startswith('data:'):
                    row['url'] = '(inline image)'
                file.write(json.dumps(row) + '\n')
        except OSError:
            log.exception('Could not write demo call log')
        if kind == 'call_ended':
            self.active_call = None

    async def __call__(self, event):
        await self.on_event(event)


def enabled():
    return os.getenv('LOG_EVENTS', 'true').lower() != 'false'


def install(bus=None, root=Path('logs')):
    if bus is None:
        from app.events import bus
    logger = CallLog(root)
    bus.subscribe(logger)
    return logger

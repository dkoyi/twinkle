"""Capture a controlled demo's event timeline and real helper screenshots.

Run before a rehearsal. This observes localhost; it does not execute actions.
Never run it during private browsing or a conversation containing real secrets.
"""
import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from urllib.request import urlopen
from websockets.asyncio.client import connect


async def capture(output, seconds=180):
    output = Path(output)
    (output / 'screenshots').mkdir(parents=True, exist_ok=True)
    (output / 'results').mkdir(exist_ok=True)
    events, images = [], []
    began = time.time()
    async with connect('ws://localhost:8000/ws/dashboard', origin='http://localhost:8000') as ws:
        try:
            async with asyncio.timeout(seconds):
                async for raw in ws:
                    event = json.loads(raw)
                    event.pop('from', None)
                    event['capture_elapsed_s'] = round(time.time() - began, 3)
                    events.append(event)
                    (output / 'results' / 'observed-events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2))
                    if event['type'] == 'screenshot':
                        def read():
                            with urlopen('http://localhost:8000/api/screenshot', timeout=5) as response:
                                return response.read()
                        jpeg = await asyncio.to_thread(read)
                        if jpeg.startswith(b'\xff\xd8'):
                            task = re.sub(r'[^a-zA-Z0-9_-]', '_', event.get('task_id', 'preview'))
                            name = f'{task}-step-{event.get("n", 0)}-{len(images):02}.jpg'
                            path = output / 'screenshots' / name
                            path.write_bytes(jpeg)
                            images.append({'file': 'screenshots/' + name, 'event': event,
                                           'source': 'Actual helper browser JPEG; fetched on screenshot event'})
                            (output / 'results' / 'screenshot-index.json').write_text(json.dumps(images, indent=2))
                    if event['type'] == 'task_finished':
                        print(json.dumps({'outcome': event.get('outcome'), 'task_id':event.get('task_id'),
                                          'duration_s':event.get('duration_s'), 'screenshots':len(images)}), flush=True)
                        break
        except TimeoutError:
            print('Capture window ended; incomplete observations are retained.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seconds', type=int, default=180)
    args = parser.parse_args()
    asyncio.run(capture(args.output, args.seconds))

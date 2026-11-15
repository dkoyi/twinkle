"""Dashboard snapshots and local demo controls for the real shared event bus."""
from copy import deepcopy
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from app.events import bus
from app.integration import bridge

router = APIRouter()


class DashboardState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = {'call': None, 'task': None, 'steps': [], 'transcript': [],
                      'pending_approval': None, 'blocked': None,
                      'speaking': False, 'screenshot_url': None, 'page_url': ''}

    def snapshot(self):
        return deepcopy(self.state)

    async def on_event(self, event):
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


state = DashboardState()


def require_local(request):
    host = request.headers.get('host', '')
    origin = request.headers.get('origin')
    if (urlsplit('http://' + host).hostname not in {'localhost', '127.0.0.1', '::1'}
            or request.headers.get('x-forwarded-host')
            or (origin and urlsplit(origin).netloc != host)):
        raise HTTPException(403, 'Use these controls from localhost on the demo laptop.')


class Goal(BaseModel):
    goal: str = Field(min_length=1, max_length=1000)


async def command(request, name, **arguments):
    require_local(request)
    if bridge.runner is None:
        raise HTTPException(503, 'The computer helper is not connected yet.')
    # Use the same event path as voice, including stop ordering and command logging.
    result = await bus.command(name, call_sid='dashboard', **arguments)
    if not result.get('ok'):
        raise HTTPException(409, result.get('message', 'The computer could not do that step.'))
    return result


@router.get('/api/state')
async def api_state():
    return state.snapshot()


@router.get('/api/screenshot')
async def screenshot():
    image = await bridge.screenshot()
    if image is None:
        raise HTTPException(404, 'No computer screenshot yet.')
    return Response(image, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})


@router.post('/api/start_task')
async def start_task(body: Goal, request: Request):
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(422, 'Tell TechTwin what you need help with.')
    return await command(request, 'start_task', goal=goal)


@router.post('/api/confirm')
async def confirm(request: Request):
    return await command(request, 'confirm_action')


@router.post('/api/cancel')
async def cancel(request: Request):
    return await command(request, 'cancel_action')


@router.post('/api/stop')
async def stop(request: Request):
    return await command(request, 'stop_task')


@router.post('/api/reset')
async def reset(request: Request):
    require_local(request)
    if bridge.runner is not None:
        await command(request, 'reset')
    await bus.publish('reset')
    return {'ok': True}

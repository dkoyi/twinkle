"""Dashboard snapshots and local demo controls for the real shared event bus."""
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from app.events import bus
from app.integration import bridge
from app import screenshots

router = APIRouter()


# Preserve the shared foundation's State API; there is one authoritative state.
from app.events import State as DashboardState
state = bus.state


class Hooks:
    """Compatibility with the team's callback registration; unset hooks fail closed."""
    start_task = confirm = cancel = stop = reset = describe = None


hooks = Hooks()
bridge.hooks = hooks


def set_screenshot(jpeg: bytes) -> str:
    if not isinstance(jpeg, bytes):
        raise TypeError('Screenshot must be JPEG bytes')
    return screenshots.set_latest(jpeg)


def clear_screenshot():
    screenshots.clear()



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
    if not bridge.available:
        raise HTTPException(503, 'The computer helper is not connected yet.')
    # Use the same event path as voice, including stop ordering and command logging.
    result = await bus.command(name, call_sid='dashboard', **arguments)
    if not result.get('ok'):
        raise HTTPException(409, result.get('message', 'The computer could not do that step.'))
    return result


@router.get('/api/state')
async def api_state():
    return {'type': 'snapshot', **state.snapshot()}


@router.get('/api/screenshot')
async def screenshot():
    image = await bridge.screenshot() or screenshots.get_latest()
    if image is None:
        return Response(status_code=204)
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
    if bridge.available:
        await command(request, 'reset')
    clear_screenshot()
    await bus.publish('reset')
    return {'ok': True}

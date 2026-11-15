import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dashboard import DashboardState
from app.events import EventBus
from app.integration import RunnerBridge, bridge
from app.call_log import CallLog


class Runner:
    def __init__(self):
        self.calls = []
        self.latest_screenshot = b'\xff\xd8fake-jpeg\xff\xd9'
    async def start(self, goal): self.calls.append(('start', goal)); return 'task-one'
    async def confirm(self): self.calls.append(('confirm',))
    async def cancel(self): self.calls.append(('cancel',))
    async def stop(self): self.calls.append(('stop',))
    async def reset(self): self.calls.append(('reset',))
    async def describe(self): return 'A search page is open.'


@pytest.fixture
def client(monkeypatch):
    runner = Runner()
    monkeypatch.setattr(bridge, 'runner', runner)
    with TestClient(app, base_url='http://localhost', headers={'host':'localhost'}) as client:
        yield client, runner


def test_dashboard_controls_reach_same_runner_as_voice(client):
    client, runner = client
    assert client.get('/dashboard').status_code == 200
    assert client.post('/api/start_task', json={'goal':'Find a video'}).json()['task_id'] == 'task-one'
    for route in ['confirm', 'cancel', 'stop', 'reset']:
        assert client.post('/api/' + route).json()['ok']
    assert runner.calls == [('start', 'Find a video'), ('confirm',), ('cancel',), ('stop',), ('reset',)]
    assert client.get('/api/screenshot').content == runner.latest_screenshot
    assert client.get('/api/screenshot').headers['cache-control'] == 'no-store'


def test_missing_runner_is_visible_and_does_not_report_success(client, monkeypatch):
    client, _ = client
    monkeypatch.setattr(bridge, 'runner', None)
    response = client.post('/api/start_task', json={'goal':'Find a video'})
    assert response.status_code == 503
    assert 'not connected' in response.json()['detail']
    assert client.get('/api/screenshot').status_code == 404
    assert client.post('/api/reset').json() == {'ok':True}


def test_remote_and_cross_site_controls_are_rejected(client):
    client, runner = client
    for headers in [{'origin':'https://evil.example'}, {'x-forwarded-host':'demo.ngrok.app'}, {'host':'demo.ngrok.app'}]:
        assert client.post('/api/start_task',json={'goal':'Do a task'},headers=headers).status_code == 403
    assert not runner.calls
    assert client.post('/api/start_task',json={'goal':'   '}).status_code == 422


@pytest.mark.asyncio
async def test_snapshot_keeps_finished_goal_and_resolves_interleaved_transcripts():
    state = DashboardState()
    async def emit(kind, **data): await state.on_event({'type':kind,'ts':100,**data})
    await emit('call_started', call_sid='call')
    await emit('task_started', task_id='one',goal='Find a recipe')
    await emit('transcript', who='caller',text='Hello',final=False)
    await emit('transcript', who='techtwin',text='Hi',final=False)
    await emit('transcript', who='caller',text='Hello there',final=True)
    await emit('step',task_id='one',n=1,status='running',summary='Opening search')
    await emit('step',task_id='one',n=1,status='done',summary='Opened search')
    await emit('needs_approval',task_id='one',question='May I play it?')
    await emit('task_finished',task_id='one',outcome='done',summary='The recipe is open')
    await emit('call_ended', call_sid='call')
    snapshot = state.snapshot()
    assert snapshot['call'] is None
    assert snapshot['task']['goal'] == 'Find a recipe' and snapshot['task']['finished']
    assert snapshot['transcript'][0]['text'] == 'Hello there'
    assert len(snapshot['transcript']) == 2 and len(snapshot['steps']) == 1
    assert snapshot['pending_approval'] is None
    await emit('blocked',task_id='one',reason='A password is needed')
    await emit('task_started',task_id='two',goal='Another task')
    assert state.snapshot()['blocked'] is None and not state.snapshot()['steps']


@pytest.mark.asyncio
async def test_bridge_stop_cancels_inflight_start():
    events = EventBus()
    adapter = RunnerBridge(events)
    started = asyncio.Event()
    class SlowRunner(Runner):
        async def start(self, goal):
            started.set()
            await asyncio.Future()
    runner = SlowRunner()
    adapter.attach(runner)
    events.subscribe(adapter.on_event)
    pending = asyncio.create_task(events.command('start_task', call_sid='call', goal='open recipe'))
    await asyncio.wait_for(started.wait(), 1)
    await events.publish('voice_command',name='stop_task',request_id=None,arguments={},call_sid='call')
    async with asyncio.timeout(1):
        while ('stop',) not in runner.calls: await asyncio.sleep(0)
    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
    await adapter.close()
    assert not adapter.workers


@pytest.mark.asyncio
async def test_logs_group_task_events_with_call_without_audio(tmp_path):
    log = CallLog(tmp_path)
    for event in [
        {'type':'call_started','ts':100,'call_sid':'browser-one'},
        {'type':'task_finished','ts':101,'task_id':'task-one','duration_s':1,'outcome':'done'},
        {'type':'audio','ts':102,'data':'must-not-be-logged'},
        {'type':'call_ended','ts':103,'call_sid':'browser-one'},
    ]:
        await log.on_event(event)
    files = list(tmp_path.rglob('*.jsonl'))
    assert len(files) == 1
    events = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert [e['type'] for e in events] == ['call_started','task_finished','call_ended']

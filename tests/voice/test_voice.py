import asyncio
import base64
from types import SimpleNamespace
import pytest
from google.genai import types
from app.config import Settings
from app.events import EventBus
from app.playback import Playback
from app.voice_brain import VoiceBrain, SYSTEM, TOOLS


class Socket:
    def __init__(self):
        self.sent = []
    async def send_json(self, message):
        self.sent.append(message)


@pytest.mark.asyncio
async def test_playback_interruption_discards_queued_audio_and_partial_pcm():
    bus, ws = EventBus(), Socket()
    playback = Playback(ws, "stream", bus, "call")
    playback.pcm(b'\0' * 1000)
    assert playback.queue.qsize() == 1
    assert len(playback.buffer) == 40
    await playback.clear()
    assert playback.queue.empty()
    assert not playback.buffer
    assert ws.sent == [{"event": "clear", "streamSid": "stream"}]


@pytest.mark.asyncio
async def test_playback_is_paced_and_marks_track_actual_playback():
    bus, ws = EventBus(), Socket()
    playback = Playback(ws, "stream", bus, "call")
    playback.pcm(b'\0' * 1920)
    playback.finish()
    task = asyncio.create_task(playback.run())
    try:
        await asyncio.sleep(.005)
        assert len(ws.sent) == 1
        await asyncio.sleep(.065)
        assert [x['event'] for x in ws.sent] == ['media', 'media', 'mark']
        assert playback.speaking
        await playback.acknowledge(ws.sent[-1]['mark']['name'])
        assert not playback.speaking
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_command_contract_and_unavailable_runner():
    bus = EventBus()
    async def runner(event):
        if event['type'] == 'voice_command':
            await bus.publish('voice_command_result', request_id=event['request_id'],
                              result={'ok': True, 'task_id': 'demo'})
    unsubscribe = bus.subscribe(runner)
    assert (await bus.command('start_task', call_sid='call', goal='open video'))['ok']
    unsubscribe()
    assert not (await bus.command('start_task', call_sid='call', timeout=.001))['ok']
    assert not bus._pending


@pytest.mark.asyncio
async def test_fragmented_stop_dispatches_immediately_without_model():
    bus, ws = EventBus(), Socket()
    playback = Playback(ws, 'stream', bus, 'call')
    brain = VoiceBrain(None, bus, playback, 'call')
    await brain.transcript('caller', 'please st')
    assert not any(e['type'] == 'voice_command' for e in bus.history)
    await brain.transcript('caller', 'op now')
    assert any(e['type'] == 'voice_command' and e['name'] == 'stop_task' for e in bus.history)
    assert ws.sent[-1]['event'] == 'clear'
    await brain.transcript('caller', '', final=True)
    assert [e for e in bus.history if e['type'] == 'transcript'][-1]['text'] == 'please stop now'


@pytest.mark.asyncio
async def test_stop_word_uses_word_boundaries():
    bus, ws = EventBus(), Socket()
    brain = VoiceBrain(None, bus, Playback(ws, 'stream', bus, 'call'), 'call')
    await brain.transcript('caller', 'Find a bus stoplight', final=True)
    assert not ws.sent


def test_config_is_valid_for_installed_gemini_sdk():
    config = types.LiveConnectConfig(response_modalities=['AUDIO'], system_instruction=SYSTEM,
                                    tools=TOOLS, input_audio_transcription={}, output_audio_transcription={})
    assert len(config.tools[0].function_declarations) == 5


class FakeLiveSession:
    def __init__(self):
        self.messages = asyncio.Queue()
        self.inputs = []
        self.responses = []
        self.greetings = []
    async def send_client_content(self, **kwargs):
        self.greetings.append(kwargs)
    async def send_realtime_input(self, **kwargs):
        self.inputs.append(kwargs)
    async def send_tool_response(self, **kwargs):
        self.responses.extend(kwargs['function_responses'])
    async def receive(self):
        message = await self.messages.get()
        yield message
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_full_mocked_gemini_session_audio_tools_transcripts_and_cleanup(monkeypatch):
    from app import voice_brain
    bus, ws = EventBus(), Socket()
    session = FakeLiveSession()
    closed = []
    async def close():
        closed.append(True)
    client = SimpleNamespace(aio=SimpleNamespace(live=SimpleNamespace(connect=lambda **kw: session), aclose=close))
    monkeypatch.setattr(voice_brain.genai, 'Client', lambda **kw: client)
    playback = Playback(ws, 'stream', bus, 'call')
    brain = VoiceBrain(SimpleNamespace(api_key='fake', live_model='fake'), bus, playback, 'call')
    async def runner(event):
        if event['type'] == 'voice_command':
            await bus.publish('voice_command_result', request_id=event['request_id'],
                              result={'ok': True, 'message': 'Started', 'task_id': 'task'})
    unsubscribe = bus.subscribe(runner)
    incoming = asyncio.Queue()
    task = asyncio.create_task(brain.run(incoming))
    try:
        await incoming.put(base64.b64encode(b'\xff' * 160).decode())
        await session.messages.put(types.LiveServerMessage(server_content=types.LiveServerContent(
            input_transcription=types.Transcription(text='Find a video', finished=True),
            output_transcription=types.Transcription(text='I can help.', finished=True),
            model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                data=b'\0' * 960, mime_type='audio/pcm;rate=24000'))]), turn_complete=True)))
        await session.messages.put(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
            function_calls=[types.FunctionCall(id='one', name='start_task', args={'goal': 'Find a video'})])))
        async with asyncio.timeout(1):
            while not session.responses:
                await asyncio.sleep(.001)
        assert session.responses[0].response['ok']
        assert session.greetings
        assert len(session.inputs[0]['audio'].data) == 640
        assert playback.queue.qsize() == 2  # Audio and end-of-turn mark.
        transcripts = [e for e in bus.history if e['type'] == 'transcript']
        assert {e['who'] for e in transcripts} == {'caller', 'techtwin'}
        assert all(e['final'] for e in transcripts)
        await session.messages.put(types.LiveServerMessage(server_content=types.LiveServerContent(interrupted=True)))
        async with asyncio.timeout(1):
            while not ws.sent:
                await asyncio.sleep(.001)
        assert playback.queue.empty()
        assert ws.sent[-1]['event'] == 'clear'
        await bus.publish('needs_approval', task_id='task', question='Shall I press Join?')
        async with asyncio.timeout(1):
            while not any('text' in item for item in session.inputs):
                await asyncio.sleep(.001)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        unsubscribe()
    assert closed and not bus._listeners and not bus._pending


@pytest.mark.asyncio
async def test_model_cannot_approve_without_a_fresh_spoken_yes():
    events, ws = EventBus(), Socket()
    brain = VoiceBrain(None, events, Playback(ws, 'stream', events, 'call'), 'call')
    brain.session = FakeLiveSession()
    async def runner(event):
        if event['type'] == 'voice_command':
            await events.publish('voice_command_result', request_id=event['request_id'], result={'ok':True})
    events.subscribe(runner)
    await brain.transcript('caller', 'yes', final=True)  # Agreement before the question is not consent.
    await brain.on_event({'type':'needs_approval', 'question':'Shall I play this video?'})
    call = SimpleNamespace(name='confirm_action',args={},id='approval')
    await brain.tool(call, brain.command_epoch)
    assert not brain.session.responses[-1].response['ok']
    assert not any(e['type'] == 'voice_command' for e in events.history)
    await brain.transcript('caller', 'yes please do not', final=True)
    await brain.tool(call, brain.command_epoch)
    assert not brain.session.responses[-1].response['ok']
    await brain.transcript('caller', 'Yes, go ahead.', final=True)
    await brain.tool(call, brain.command_epoch)
    assert brain.session.responses[-1].response['ok']
    await brain.on_event({'type':'approval_result', 'approved':True})
    before = sum(e['type'] == 'voice_command' for e in events.history)
    await brain.tool(call, brain.command_epoch)
    assert brain.session.responses[-1].response['ok']
    assert sum(e['type'] == 'voice_command' for e in events.history) == before


@pytest.mark.asyncio
async def test_stop_stays_latched_until_a_new_caller_turn():
    events, ws = EventBus(), Socket()
    brain = VoiceBrain(None, events, Playback(ws, 'stream', events, 'call'), 'call')
    brain.session = FakeLiveSession()
    await brain.transcript('caller', 'stop', final=True)
    call = SimpleNamespace(name='start_task',args={'goal':'Open a video'},id='late-start')
    await brain.tool(call, brain.command_epoch)
    assert not brain.session.responses[-1].response['ok']
    assert brain.stopped
    await brain.transcript('caller', 'Help me with something else', final=True)
    assert not brain.stopped


@pytest.mark.asyncio
async def test_spoken_yes_directly_resolves_real_pending_approval():
    from app.integration import RunnerBridge
    events, ws = EventBus(), Socket()
    brain = VoiceBrain(None, events, Playback(ws, 'stream', events, 'call'), 'call')
    brain.session = FakeLiveSession()
    adapter = RunnerBridge(events)
    calls = []
    class Runner:
        async def confirm(self, by='voice'):
            calls.append(by)
            await events.publish('approval_result', task_id='one', approved=True, by=by)
            return True
    adapter.attach(Runner())
    events.subscribe(adapter.on_event)
    events.subscribe(brain.on_event)
    await events.publish('needs_approval', task_id='one', step_n=1, question='Shall I play?')
    await brain.transcript('caller', 'Yes, go ahead.', final=True)
    assert calls == ['voice']
    assert events.state.pending_approval is None
    await brain.tool(SimpleNamespace(name='confirm_action', args={}, id='late'), brain.command_epoch)
    assert calls == ['voice']  # A later model tool cannot execute the click twice.

import asyncio
import base64
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app import browser_voice
from app.events import bus
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-server-key')
    bus.history.clear()
    with TestClient(app, base_url='http://localhost', headers={'host': 'localhost'}) as client:
        yield client


def test_demo_page_and_assets(client):
    page = client.get('/talk')
    assert page.status_code == 200 and 'Start talking' in page.text
    assert 'fake-server-key' not in page.text
    assert client.get('/voice-demo/microphone.js').status_code == 200


@pytest.mark.parametrize('headers', [
    {}, {'origin': 'https://untrusted.example'},
    {'origin': 'http://localhost', 'x-forwarded-host': 'public.ngrok.app'},
])
def test_only_local_same_origin_can_start_voice(client, headers):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws/voice', headers=headers):
            pass


def test_missing_key_reports_actionable_error(client, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', '')
    with client.websocket_connect('/ws/voice', headers={'origin': 'http://localhost'}) as ws:
        assert 'GEMINI_API_KEY' in ws.receive_json()['message']


def test_browser_pcm_transport_and_hangup_cleanup(client, monkeypatch):
    received = []
    class FakeBrain:
        def __init__(self, settings, events, playback, call_sid, *, decode_audio):
            self.events, self.playback, self.call_sid, self.decode_audio = events, playback, call_sid, decode_audio
        async def run(self, incoming):
            await self.events.publish('voice_ready', call_sid=self.call_sid)
            received.append(self.decode_audio(await incoming.get()))
            self.playback.pcm(b'\x01\x00' * 480)
            self.playback.finish()
            await asyncio.Future()
    monkeypatch.setattr(browser_voice, 'VoiceBrain', FakeBrain)
    with client.websocket_connect('/ws/voice', headers={'origin': 'http://localhost'}) as ws:
        assert ws.receive_json()['type'] == 'voice_ready'
        ws.send_bytes(b'\0' * 640)
        audio = ws.receive_json()
        assert audio['type'] == 'audio' and audio['rate'] == 24000
        assert base64.b64decode(audio['data']) == b'\x01\x00' * 480
        assert ws.receive_json()['type'] == 'audio_end'
        ws.send_json({'type': 'end'})
        # A speaking event can be queued before the socket closes.
        with pytest.raises(WebSocketDisconnect):
            while True:
                ws.receive_json()
    assert received == [b'\0' * 640]
    assert any(e['type'] == 'call_ended' for e in bus.history)
    assert any(e['type'] == 'voice_command' and e['name'] == 'stop_task' for e in bus.history)


def test_stop_button_clears_speech_and_dispatches_stop(client, monkeypatch):
    class FakeBrain:
        def __init__(self, *args, **kwargs): pass
        async def run(self, incoming): await asyncio.Future()
    monkeypatch.setattr(browser_voice, 'VoiceBrain', FakeBrain)
    with client.websocket_connect('/ws/voice', headers={'origin': 'http://localhost'}) as ws:
        ws.send_json({'type': 'stop'})
        assert ws.receive_json()['type'] == 'clear'
        ws.send_json({'type': 'end'})
        with pytest.raises(WebSocketDisconnect):
            while True: ws.receive_json()
    assert sum(e['type'] == 'voice_command' and e['name'] == 'stop_task' for e in bus.history) == 2

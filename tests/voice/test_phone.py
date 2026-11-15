import base64
from xml.etree import ElementTree
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from twilio.request_validator import RequestValidator
from app.events import bus
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://demo.ngrok-free.app')
    monkeypatch.setenv('VOICE_MODE', 'echo')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'test-token')
    monkeypatch.setenv('TWILIO_VALIDATE_SIGNATURES', 'true')
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest')
    bus.history.clear()
    with TestClient(app) as client:
        yield client


def sign(path, data=None):
    return {'X-Twilio-Signature': RequestValidator('test-token').compute_signature(
        'https://demo.ngrok-free.app' + path, data or {})}


def start():
    return {'event': 'start', 'start': {'callSid': 'CAcall', 'streamSid': 'MZstream',
            'accountSid': 'ACtest', 'customParameters': {'caller_last4': '1234'},
            'mediaFormat': {'encoding': 'audio/x-mulaw', 'sampleRate': 8000, 'channels': 1}}}


def test_signed_webhook_and_no_caller_number_leak(client):
    form = {'From': '+15555551234'}
    assert client.post('/voice', data=form).status_code == 403
    response = client.post('/voice', data=form, headers=sign('/voice', form))
    assert response.status_code == 200
    root = ElementTree.fromstring(response.text)
    stream = root.find('Connect/Stream')
    assert stream.attrib['url'] == 'wss://demo.ngrok-free.app/media'
    assert stream.find('Parameter').attrib['value'] == '1234'
    assert '+15555551234' not in response.text


def test_websocket_auth(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/media'):
            pass


def test_phone_echo_and_cleanup(client):
    payload = base64.b64encode(b'\xff' * 160).decode()
    with client.websocket_connect('/media', headers=sign('/media')) as ws:
        ws.send_json({'event': 'connected'})
        ws.send_json(start())
        ws.send_json({'event': 'media', 'media': {'payload': payload, 'track': 'inbound'}})
        assert ws.receive_json() == {'event': 'media', 'streamSid': 'MZstream', 'media': {'payload': payload}}
        ws.send_json({'event': 'stop'})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    kinds = [e['type'] for e in bus.history]
    assert 'call_started' in kinds and 'call_ended' in kinds and 'voice_command' in kinds
    assert next(e for e in bus.history if e['type'] == 'call_started')['from'] == '1234'


def test_hangup_without_stop_still_ends_call(client):
    with client.websocket_connect('/media', headers=sign('/media')) as ws:
        ws.send_json(start())
        ws.send_json({'event': 'media', 'media': {'payload': base64.b64encode(b'\xff' * 160).decode()}})
        ws.receive_json()
    assert any(e['type'] == 'call_ended' for e in bus.history)


def test_dashboard_snapshot_and_events(client):
    with client.websocket_connect('/ws/dashboard') as ws:
        message = ws.receive_json()
        assert message['type'] == 'snapshot'
        assert message['pending_approval'] is None
    assert client.get('/api/state').status_code == 200
    assert client.get('/').json()['message'] == 'TechTwin is running'

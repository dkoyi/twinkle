from functools import partial

import pytest
from fastapi.testclient import TestClient

from app.events import bus
from app.main import app
from app.integration import bridge


class TestRunner:
    __test__ = False

    async def start(self, goal):
        await bus.publish('task_started', task_id='test', goal=goal)
        return 'test'

    async def confirm(self, by='dashboard'):
        p = bus.state.pending_approval
        if p:
            await bus.publish('approval_result', task_id=p['task_id'], approved=True, by=by)

    async def stop(self): pass
    async def reset(self): pass


def receive_type(ws, kind):
    while True:
        event = ws.receive_json()
        if event['type'] == kind:
            return event


@pytest.fixture
def client(monkeypatch):
    bus.state.reset()
    monkeypatch.setattr(bridge, 'runner', TestRunner())
    with TestClient(app, base_url='http://localhost', headers={'host': 'localhost'}) as c:
        yield c


def test_pages_are_served(client):
    assert client.get("/").status_code == 200
    page = client.get("/dashboard")
    assert page.status_code == 200 and "TechTwin" in page.text
    assert client.get("/static/dashboard.css").status_code == 200
    assert client.get("/static/dashboard.js").status_code == 200


def test_state_endpoint_and_empty_screenshot(client):
    snap = client.get("/api/state").json()
    assert snap["type"] == "snapshot" and snap["steps"] == [] and snap["pending_approval"] is None
    assert client.get("/api/screenshot").status_code == 204


def test_websocket_sends_snapshot_then_live_events(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        assert client.post("/api/start_task", json={"goal": "play a video"}).json()["ok"] is True
        ev = receive_type(ws, 'task_started')
        assert ev["type"] == "task_started" and ev["goal"] == "play a video"


def test_start_task_needs_a_goal(client):
    assert client.post("/api/start_task", json={"goal": "  "}).status_code == 422


def test_confirm_resolves_pending_approval(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        ws.receive_json()
        client.portal.call(partial(bus.publish, "needs_approval", task_id="t", step_n=1, question="Shall I?", reason="r"))
        assert ws.receive_json()["type"] == "needs_approval"
        client.post("/api/confirm")
        ev = receive_type(ws, 'approval_result')
        assert ev["type"] == "approval_result" and ev["approved"] is True
    assert bus.state.pending_approval is None


def test_reset_endpoint_clears_state(client):
    client.portal.call(partial(bus.publish, "task_started", task_id="t", goal="g"))
    assert client.get("/api/state").json()["task"]["goal"] == "g"
    client.post("/api/reset")
    assert client.get("/api/state").json()["task"] is None

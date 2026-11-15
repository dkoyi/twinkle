"""The Twinkle front end: pages are served, assets load, and every element id a script looks up exists."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    with TestClient(app, base_url="http://localhost", headers={"host": "localhost"}) as c:
        yield c


@pytest.mark.parametrize("path", ["/", "/talk", "/dashboard", "/family", "/help", "/classic"])
def test_pages_are_served(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", [
    "/static/phone.css", "/static/phone.js", "/static/voice.js", "/static/demo.js",
    "/static/dashboard.css", "/static/dashboard.js", "/static/mascot.js",
    "/static/twinkle.js", "/static/twinkle.css",
    "/static/assets/favicon.svg", "/static/assets/twinkle-idle-still.svg",
    "/static/fonts/baloo-2-latin-800-normal.woff2",
    "/static/fonts/atkinson-hyperlegible-next-latin-400-normal.woff2",
    "/voice-demo/microphone.js",
])
def test_assets_are_served(client, path):
    assert client.get(path).status_code == 200


def test_phone_page_carries_the_real_call(client):
    page = client.get("/talk").text
    assert "Call Twinkle" in page
    # voice.js (the real microphone and audio) must load before phone.js uses it
    assert page.index("voice.js") < page.index("phone.js")


def _ids_used(script_path, pattern):
    return set(re.findall(pattern, (ROOT / script_path).read_text(encoding="utf-8")))


@pytest.mark.parametrize("route, script", [
    ("/talk", "static/phone.js"),
    ("/dashboard", "static/dashboard.js"),
    ("/classic", "voice_demo/talk.js"),
])
def test_every_element_id_a_script_uses_exists(client, route, script):
    page = client.get(route).text
    ids = _ids_used(script, r"\$\(['\"]([A-Za-z0-9]+)['\"]\)")
    assert ids, f"no ids found in {script}"
    built = {"history", "recentSteps"}  # family page only; dashboard.js skips them when absent
    missing = sorted(i for i in ids - built if f'id="{i}"' not in page)
    assert not missing, f"{script} needs these ids on {route}: {missing}"

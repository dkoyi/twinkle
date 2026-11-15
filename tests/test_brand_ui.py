"""Guards for the front end: assets are served, pages load the brand layer, and the element ids
that Maulik's scripts drive still exist. A redesign may change any look, never these names."""
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


@pytest.mark.parametrize("path", [
    "/static/brand/brand.css", "/static/brand/twinkle.js", "/static/brand/widget.js",
    "/static/brand/favicon.svg", "/static/fonts/Baloo2.woff2", "/static/fonts/AtkinsonNext.woff2",
    "/voice-demo/style.css", "/voice-demo/talk.js",
])
def test_brand_assets_are_served(client, path):
    assert client.get(path).status_code == 200


def test_phone_page_is_the_twinkle_page(client):
    page = client.get("/talk").text
    assert "Call Twinkle" in page and "No telephone call is placed" in page
    assert "/static/brand/widget.js" in page and "/static/brand/brand.css" in page
    assert 'id="phoneTwinkle"' in page


def test_dashboard_feeds_the_floating_twinkle(client):
    page = client.get("/dashboard").text
    assert "data-feeds-widget" in page and "/static/brand/widget.js" in page
    assert 'id="emptyMascot"' in page


def _ids_used(script_path, pattern):
    return set(re.findall(pattern, (ROOT / script_path).read_text(encoding="utf-8")))


def test_every_element_id_the_phone_script_uses_exists(client):
    page = client.get("/talk").text
    ids = _ids_used("voice_demo/talk.js", r"\$\('([A-Za-z]+)'\)")
    assert ids, "no ids found: update this test if talk.js changed how it looks elements up"
    missing = sorted(i for i in ids if f'id="{i}"' not in page)
    assert not missing, f"talk.js needs these ids in voice_demo/index.html: {missing}"


def test_every_element_id_the_dashboard_script_uses_exists(client):
    page = client.get("/dashboard").text
    ids = _ids_used("static/dashboard.js", r'\$\("([A-Za-z]+)"\)')
    assert ids
    missing = sorted(i for i in ids if f'id="{i}"' not in page)
    assert not missing, f"dashboard.js needs these ids in static/dashboard.html: {missing}"


def test_the_widget_is_not_added_inside_the_embedded_dashboard():
    text = (ROOT / "static/brand/widget.js").read_text(encoding="utf-8")
    assert "window.self !== window.top" in text

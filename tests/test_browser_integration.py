"""Real headless Chromium against tiny local pages. Skipped if Chromium isn't installed."""
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import quote

import pytest

from app import safety
from app.actions import Action
from app.browser import Browser

pytest.importorskip("playwright")


def page_url(body: str) -> str:
    return "data:text/html," + quote(f"<!doctype html><meta charset=utf-8><body style='margin:0'>{body}</body>")


@asynccontextmanager
async def browser(monkeypatch):
    monkeypatch.setenv("HEADLESS", "true")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("FAKE_MEDIA", "false")
    b = Browser()
    try:
        await b.start()
    except Exception as exc:  # no Chromium on this machine
        pytest.skip(f"Chromium not available: {exc!r}")
    try:
        yield b
    finally:
        await b.stop()


def run(coro):
    return asyncio.run(coro)


def at(x_px, y_px, kind="click", **kw):
    """Build an action at pixel coordinates on the 1280x800 page."""
    return Action(kind, nx=x_px / 1280 * 1000, ny=y_px / 800 * 1000, name=kind, **kw)


def test_screenshots_are_real_images(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            await b.goto(page_url("<h1>Hello</h1>"))
            return await b.screenshot_png(), await b.screenshot_jpeg()

    png, jpg = run(go())
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and jpg[:2] == b"\xff\xd8"


def test_visible_password_field_is_detected_and_blocked(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            await b.goto(page_url("<input type=password style='width:200px;height:30px'>"))
            return await safety.check(Action("click", nx=1, ny=1), b.page)

    v = run(go())
    assert v.kind == "block" and "password" in v.reason


def test_hidden_password_field_is_ignored(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            await b.goto(page_url("<input type=password style='display:none'><p>Welcome</p>"))
            return await safety.check_page(b.page)

    assert run(go()).kind == "allow"


def test_card_fields_are_detected_two_ways(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            await b.goto(page_url("<input autocomplete='cc-number' style='width:200px;height:30px'>"))
            a = await safety.check_page(b.page)
            await b.goto(page_url("<label for=c>Card number</label><input id=c style='width:200px;height:30px'>"))
            c = await safety.check_page(b.page)
            return a, c

    a, c = run(go())
    assert a.kind == "block" and c.kind == "block" and "card details" in c.reason


def test_a_join_button_asks_first_using_its_real_label(monkeypatch):
    html = "<button style='position:absolute;left:100px;top:100px;width:200px;height:60px'>Join Meeting</button>"

    async def go():
        async with browser(monkeypatch) as b:
            await b.goto(page_url(html))
            a = at(200, 130)
            return await safety.check(a, b.page), await safety.label_for(a, b.page)

    v, label = run(go())
    assert v.kind == "ask_first" and v.question == "Shall I press Join Meeting?" and label == "Join Meeting"


def test_a_search_box_with_enter_does_not_ask_but_a_join_form_does(monkeypatch):
    search = ("<form action='#'><input id=q style='position:absolute;left:100px;top:100px;width:300px;height:40px'>"
              "<button type=submit style='position:absolute;left:420px;top:100px'>Search</button></form>")
    join = search.replace("Search", "Join now")

    async def go():
        async with browser(monkeypatch) as b:
            act = at(250, 120, "type", text="dal", press_enter=True)
            await b.goto(page_url(search))
            s = await safety.check(act, b.page)
            await b.goto(page_url(join))
            j = await safety.check(act, b.page)
            return s, j

    s, j = run(go())
    assert s.kind == "allow" and j.kind == "ask_first"


def test_mouse_and_keyboard_actions_really_work(monkeypatch):
    html = ("<input id=box style='position:absolute;left:100px;top:100px;width:300px;height:40px'>"
            "<button id=go onclick=\"document.title='clicked'\" "
            "style='position:absolute;left:100px;top:200px;width:200px;height:60px'>Go</button>"
            "<div style='height:3000px'></div>")

    async def go():
        async with browser(monkeypatch) as b:
            await b.goto(page_url(html))
            await b.execute(at(250, 120, "type", text="dal recipe"))
            typed = await b.page.input_value("#box")
            await b.execute(at(250, 120, "type", text="replaced"))     # clears first
            replaced = await b.page.input_value("#box")
            await b.execute(at(200, 230))
            title = await b.page.title()
            await b.execute(Action("scroll", direction="down", amount=500, name="scroll_document"))
            scrolled = await b.page.evaluate("window.scrollY")
            await b.execute(Action("key", keys="Control+A", name="key_combination"))
            return typed, replaced, title, scrolled

    typed, replaced, title, scrolled = run(go())
    assert typed == "dal recipe" and replaced == "replaced" and title == "clicked" and scrolled >= 400


def test_new_tabs_are_followed_and_reset_closes_them(monkeypatch):
    html = ("<button onclick=\"var w=window.open('about:blank');w.document.write('<h1>New tab</h1>')\" "
            "style='position:absolute;left:100px;top:100px;width:200px;height:60px'>Open</button>")

    async def go():
        async with browser(monkeypatch) as b:
            await b.goto(page_url(html))
            first = b.page
            await b.execute(at(200, 130))
            await asyncio.sleep(0.3)
            followed = b.page is not first
            await b.reset()
            return followed, len([p for p in b._context.pages if not p.is_closed()])

    followed, open_tabs = run(go())
    assert followed and open_tabs == 1


def test_a_bad_action_raises_a_friendly_error_not_a_crash(monkeypatch):
    from app.browser import BrowserError

    async def go():
        async with browser(monkeypatch) as b:
            with pytest.raises(BrowserError):
                await b.execute(Action("click", name="click_at"))          # no coordinates
            with pytest.raises(BrowserError):
                await b.execute(Action("unknown", name="do_a_barrel_roll"))

    run(go())


def test_start_recovers_after_helper_browser_is_closed(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            await b._browser.close()
            assert not b.started
            await b.start()
            assert b.started
            assert (await b.screenshot_png()).startswith(b'\x89PNG')
    run(go())


def test_start_recovers_after_last_tab_is_closed(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            await b.page.close()
            assert not b.started
            await b.start()
            assert b.started
            assert (await b.screenshot_png()).startswith(b'\x89PNG')
    run(go())


def test_repeated_preview_capture_keeps_one_browser_and_one_tab(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            original = b._browser
            await b.goto(page_url('<h1>Stable helper</h1>'))
            for _ in range(5):
                png, jpg = await asyncio.gather(b.screenshot_png(), b.screenshot_jpeg())
                assert png.startswith(b'\x89PNG') and jpg.startswith(b'\xff\xd8')
                assert b._browser is original and b.started
                assert len(b._context.pages) == 1
    run(go())


def test_new_helper_tab_replaces_previous_tab(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            previous = b.page
            new = await b._context.new_page()
            for _ in range(50):
                if previous.is_closed():
                    break
                await asyncio.sleep(.01)
            assert previous.is_closed()
            assert b.page is new
            assert len(b._context.pages) == 1
    run(go())


def test_live_preview_uses_streamed_frames_without_repeated_screenshots_or_resizes(monkeypatch):
    async def go():
        async with browser(monkeypatch) as b:
            await b.goto(page_url('<h1>Preview A</h1>'))
            first = await b.screenshot_jpeg()
            assert first.startswith(b'\xff\xd8')
            session = b._capture_session
            send = session.send
            commands = []
            async def observe(method, params=None):
                commands.append(method)
                return await send(method, params)
            monkeypatch.setattr(session, 'send', observe)
            async def no_playwright_capture(*args, **kwargs):
                pytest.fail('Preview must not call page.screenshot')
            monkeypatch.setattr(b.page, 'screenshot', no_playwright_capture)
            await b.page.evaluate('''() => {
                window.previewResizes = 0;
                window.addEventListener('resize', () => window.previewResizes++);
                document.body.style.background = 'rgb(10, 80, 150)';
                document.querySelector('h1').textContent = 'Preview B';
            }''')
            for _ in range(50):
                latest = await b.screenshot_jpeg()
                if latest != first:
                    break
                await asyncio.sleep(.05)
            assert latest != first, 'Stream should deliver the changed page'
            for _ in range(10):
                assert await b.screenshot_jpeg() == latest
            assert 'Page.captureScreenshot' not in commands
            assert not any('Emulation.' in method for method in commands)
            assert await b.page.evaluate('window.previewResizes') == 0
    run(go())

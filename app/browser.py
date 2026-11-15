"""The visible Chromium browser that TechTwin drives (Playwright).

One browser and one context for the whole server lifetime, launched once at startup.
The window is never hidden: judges watch it move.
"""
from __future__ import annotations

import asyncio
import base64
import sys
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, Page, async_playwright

from app.actions import Action, px
from app.settings import get_settings

SELECT_ALL = "Meta+A" if sys.platform == "darwin" else "Control+A"


class BrowserError(Exception):
    """An action could not be carried out (bad element, timeout...). The runner recovers."""


class Browser:
    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self.recordings: list[str] = []
        self._screenshot_lock = asyncio.Lock()
        self._capture_session = None
        self._capture_page = None
        self._preview_jpeg = None
        self._frame_ready = asyncio.Event()

    # ---------- lifecycle ----------
    async def start(self) -> None:
        if self._context:
            if self._browser and self._browser.is_connected():
                if self._page is None or self._page.is_closed():
                    self._page = await self._context.new_page()
                    await self.go_start()
                return
            # Closing the helper window disconnects Chromium but leaves Python
            # handles behind. Dispose those before launching a fresh helper.
            await self.stop()
        s = get_settings()
        args = ["--window-position=0,0"]
        if s.fake_media:
            args += ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=s.headless, args=args)
        recording = {}
        if os.getenv('DEMO_RECORD_VIDEO', 'false').lower() == 'true':
            root = Path(os.getenv('DEMO_RECORD_DIR', 'demo-artifacts/recordings'))
            root.mkdir(parents=True, exist_ok=True)
            recording = {'record_video_dir': str(root),
                         'record_video_size': {'width': s.viewport_w, 'height': s.viewport_h}}
        self._context = await self._browser.new_context(
            viewport={"width": s.viewport_w, "height": s.viewport_h},
            accept_downloads=False,
            locale="en-US",
            **recording,
        )
        self._context.on("page", self._on_new_page)
        self._page = await self._context.new_page()
        self._watch(self._page)
        await self.go_start()

    async def stop(self) -> None:
        try:
            await self._stop_capture()
            if self._context and self._browser and self._browser.is_connected():
                videos = [page.video for page in self._context.pages if page.video]
                await self._context.close()
                for video in videos:
                    self.recordings.append(str(await video.path()))
            if self._browser and self._browser.is_connected():
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        finally:
            self._pw = self._browser = self._context = self._page = None

    @property
    def started(self) -> bool:
        return bool(self._context and self._browser and self._browser.is_connected()
                    and self._page and not self._page.is_closed())

    # ---------- pages / tabs ----------
    def _watch(self, page: Page) -> None:
        # Pop-up dialogs (alert, "leave this page?") are dismissed so they can't freeze the run.
        page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        page.on("close", lambda _p: self._on_close(_p))

    def _on_new_page(self, page: Page) -> None:
        """Follow a newly opened link, keeping only one helper tab."""
        previous = self._page
        self._watch(page)
        self._page = page
        if previous and previous is not page and not previous.is_closed():
            asyncio.create_task(self._close_previous(previous))

    async def _close_previous(self, page: Page) -> None:
        try:
            await page.close()
        except Exception:
            pass

    def _on_close(self, page: Page) -> None:
        if self._page is page and self._context:
            alive = [p for p in self._context.pages if not p.is_closed()]
            self._page = alive[-1] if alive else None

    @property
    def page(self) -> Page:
        if not self._page or self._page.is_closed():
            raise BrowserError("The browser window isn't open.")
        return self._page

    @property
    def url(self) -> str:
        try:
            return self.page.url
        except BrowserError:
            return ""

    # ---------- screenshots ----------
    async def _stop_capture(self) -> None:
        session = self._capture_session
        self._capture_session = self._capture_page = None
        self._preview_jpeg = None
        self._frame_ready.clear()
        if session:
            try:
                await session.detach()
            except Exception:
                pass

    async def _ensure_capture(self):
        page = self.page
        if self._capture_page is page and self._capture_session:
            return self._capture_session
        await self._stop_capture()
        session = await self._context.new_cdp_session(page)
        self._capture_session, self._capture_page = session, page

        async def frame(event):
            if session is not self._capture_session:
                return
            self._preview_jpeg = base64.b64decode(event['data'])
            self._frame_ready.set()
            try:
                # Chrome permits only a few unacknowledged frames. Delay the
                # acknowledgment to bound preview work even on playing video.
                await asyncio.sleep(.2)
                await session.send('Page.screencastFrameAck', {'sessionId': event['sessionId']})
            except Exception:
                pass  # The tab may have closed while a frame was in flight.

        session.on('Page.screencastFrame', frame)
        try:
            await session.send('Page.startScreencast', {
                'format': 'jpeg', 'quality': 70, 'maxWidth': get_settings().viewport_w,
                'maxHeight': get_settings().viewport_h, 'everyNthFrame': 1,
            })
        except Exception:
            await self._stop_capture()
            raise
        return session

    async def screenshot_png(self) -> bytes:
        async with self._screenshot_lock:
            session = await self._ensure_capture()
            try:
                await asyncio.wait_for(self._frame_ready.wait(), 3)
            except asyncio.TimeoutError:
                raise BrowserError('Waiting for the browser to finish drawing.') from None
            # The model needs a fresh still for each decision. Capture directly
            # from the compositor without Playwright's screenshot preparation
            # (which temporarily changes page/viewport state).
            result = await asyncio.wait_for(session.send('Page.captureScreenshot', {
                'format': 'png', 'fromSurface': True, 'captureBeyondViewport': False,
            }), 5)
            return base64.b64decode(result['data'])

    async def screenshot_jpeg(self, quality: int = 70) -> bytes:
        async with self._screenshot_lock:
            await self._ensure_capture()
            try:
                await asyncio.wait_for(self._frame_ready.wait(), 3)
            except asyncio.TimeoutError:
                raise BrowserError('Waiting for the next live browser frame.') from None
            # Preview reads never trigger a screenshot, resize or focus change.
            return self._preview_jpeg

    async def pause_media(self) -> None:
        if self.started:
            await self.page.evaluate("() => document.querySelectorAll('video,audio').forEach(media => media.pause())")

    async def media_state(self) -> dict:
        return await self.page.evaluate('''() => {
            const v = document.querySelector('video');
            return v ? {present:true, paused:v.paused, current_time:v.currentTime,
                ready_state:v.readyState, ended:v.ended} : {present:false};
        }''')

    # ---------- navigation ----------
    async def goto(self, url: str) -> None:
        if "://" not in url and not url.startswith(("about:", "data:")):
            url = "https://" + url
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except Exception as exc:
            raise BrowserError(f"Couldn't open that page: {exc}") from exc

    async def go_start(self) -> None:
        s = get_settings()
        try:
            await self.page.goto(s.start_url if s.demo_mode else "about:blank",
                                 wait_until="domcontentloaded", timeout=5000)
        except Exception:
            await self.page.goto("about:blank")

    async def reset(self) -> None:
        """Close extra tabs and return to the clean start page."""
        if not self._context:
            return
        pages = [p for p in self._context.pages if not p.is_closed()]
        keep = pages[0] if pages else await self._context.new_page()
        for p in pages[1:]:
            try:
                await p.close()
            except Exception:
                pass
        self._page = keep
        await self.go_start()

    # ---------- actions ----------
    async def _settle(self) -> None:
        """Give the page a moment to react, like a person waiting for it to load."""
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        await asyncio.sleep(0.8)

    async def execute(self, a: Action) -> None:
        s = get_settings()
        w, h = s.viewport_w, s.viewport_h
        try:
            p = self.page
            x = px(a.nx, w) if a.nx is not None else None
            y = px(a.ny, h) if a.ny is not None else None

            if a.kind in ("click", "double_click", "right_click", "hover"):
                if x is None or y is None:
                    raise BrowserError("The model didn't say where to click.")
                await p.mouse.move(x, y, steps=12)  # a visible glide before the click
                if a.kind == "click":
                    await p.mouse.click(x, y)
                elif a.kind == "double_click":
                    await p.mouse.dblclick(x, y)
                elif a.kind == "right_click":
                    await p.mouse.click(x, y, button="right")

            elif a.kind == "type":
                if x is not None and y is not None:
                    await p.mouse.move(x, y, steps=10)
                    await p.mouse.click(x, y)
                    if a.clear:
                        await p.keyboard.press(SELECT_ALL)
                        await p.keyboard.press("Backspace")
                await p.keyboard.type(a.text or "", delay=35)
                if a.press_enter:
                    await p.keyboard.press("Enter")

            elif a.kind == "scroll":
                if x is not None and y is not None:
                    await p.mouse.move(x, y)
                amount = max(100, min(a.amount, 1500))
                dx, dy = {"up": (0, -amount), "down": (0, amount),
                          "left": (-amount, 0), "right": (amount, 0)}.get(a.direction, (0, amount))
                await p.mouse.wheel(dx, dy)

            elif a.kind == "navigate":
                await self.goto(a.url or "")

            elif a.kind == "key":
                await p.keyboard.press(a.keys or "Enter")

            elif a.kind == "wait":
                await asyncio.sleep(max(0.5, min(a.seconds, 5.0)))

            elif a.kind == "back":
                await p.go_back(wait_until="domcontentloaded", timeout=5000)

            elif a.kind == "forward":
                await p.go_forward(wait_until="domcontentloaded", timeout=5000)

            elif a.kind == "drag":
                if None in (x, y, a.end_nx, a.end_ny):
                    raise BrowserError("The model didn't say where to drag.")
                await p.mouse.move(x, y)
                await p.mouse.down()
                await p.mouse.move(px(a.end_nx, w), px(a.end_ny, h), steps=15)
                await p.mouse.up()

            elif a.kind == "noop":
                pass
            else:
                raise BrowserError(f"I don't know how to do '{a.name}'.")
        except BrowserError:
            raise
        except Exception as exc:  # Playwright timeouts, closed pages, etc.
            raise BrowserError(str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__) from exc
        await self._settle()

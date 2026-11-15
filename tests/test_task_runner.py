"""The whole loop, with a fake browser and a scripted model: no key, no real browser."""
import asyncio

import pytest

from app import safety
from app.actions import Action
from app.browser import BrowserError
from app.computer_use import ActionResult, Proposal, ProviderError, ScriptedProvider
from app.events import EventBus
from app.task_runner import TaskBusy, TaskRunner

START = "http://localhost:8000/static/start.html"


class FakePage:
    def __init__(self, browser):
        self.b = browser
        self.page_probe = {"password": False, "card": False}
        self.element_probe = {"text": "", "form": "", "tag": "div"}

    @property
    def url(self):
        return self.b.url

    async def evaluate(self, js, arg=None):
        return self.page_probe if js == safety.PAGE_PROBE_JS else self.element_probe


class FakeBrowser:
    started = True

    def __init__(self):
        self.url = START
        self.page = FakePage(self)
        self.executed: list[Action] = []
        self.fail_next = 0
        self.land_on: str | None = None   # where the next action takes us
        self.resets = 0

    async def screenshot_png(self):
        return b"png"

    async def screenshot_jpeg(self, quality=70):
        return b"jpeg"

    async def execute(self, a):
        if self.fail_next:
            self.fail_next -= 1
            raise BrowserError("no such element")
        self.executed.append(a)
        if self.land_on:
            self.url, self.land_on = self.land_on, None

    async def reset(self):
        self.resets += 1
        self.url = START


def make(proposals, browser=None, provider=None):
    browser = browser or FakeBrowser()
    bus = EventBus()
    events = []

    async def collect(ev):
        events.append(ev)

    bus.subscribe(collect)
    sp = provider or ScriptedProvider(proposals)
    runner = TaskRunner(browser, provider_factory=lambda: sp, event_bus=bus)
    return runner, browser, bus, events, sp


def types(events):
    return [e["type"] for e in events]


def finished(events):
    return next(e for e in reversed(events) if e["type"] == "task_finished")


async def drain(runner):
    await runner._task
    await asyncio.sleep(0.02)  # let listeners see the last events


async def until(cond, timeout=2.0):
    end = asyncio.get_event_loop().time() + timeout
    while not cond():
        assert asyncio.get_event_loop().time() < end, "timed out waiting"
        await asyncio.sleep(0.01)


def run(coro):
    return asyncio.run(coro)


def click(x=500, y=500, name="click_at"):
    return Action("click", nx=x, ny=y, name=name, call_id="c")


def nav(url="https://www.youtube.com"):
    return Action("navigate", url=url, name="navigate", call_id="n")


# ------------------------------------------------------------------ happy path
def test_a_simple_task_runs_to_done_and_reports_in_plain_words():
    async def go():
        runner, browser, bus, events, _ = make([Proposal([nav()]), Proposal(text="**The video** is playing now. Enjoy!")])
        tid = await runner.start("play a video")
        await drain(runner)
        return tid, browser, events

    tid, browser, events = run(go())
    assert tid.startswith('t-') and len(browser.executed) == 1
    ts = types(events)
    assert ts[0] == "task_started" and ts[-1] == "task_finished"
    assert "screenshot" in ts
    steps = [e for e in events if e["type"] == "step"]
    assert [s["status"] for s in steps] == ["running", "done"]
    assert steps[0]["summary"] == "Opening youtube.com" and steps[1]["summary"] == "Opened youtube.com"
    fin = finished(events)
    assert fin["outcome"] == "done" and fin["summary"] == "The video is playing now. Enjoy!" and fin["steps"] == 1


def test_clicks_carry_a_point_for_the_dashboard_ripple():
    async def go():
        runner, b, bus, events, _ = make([Proposal([click(250, 750)]), Proposal(text="Done.")])
        await runner.start("x")
        await drain(runner)
        return events

    first = next(e for e in go_events(go) if e["type"] == "step")
    assert first["point"] == {"x": 0.25, "y": 0.75}


def go_events(go):
    return run(go())


# ------------------------------------------------------------------ approvals
def test_ask_first_waits_for_a_yes_then_acts():
    async def go():
        runner, browser, bus, events, _ = make([Proposal([click()]), Proposal(text="You're in.")])
        browser.page.element_probe = {"text": "Join Meeting", "form": "", "tag": "button"}
        await runner.start("join the meeting")
        await until(lambda: bus.state.pending_approval is not None)
        assert browser.executed == []                      # nothing happened yet
        assert bus.state.pending_approval["question"] == "Shall I press Join Meeting?"
        assert await runner.confirm(by="voice") is True
        await drain(runner)
        return browser, events

    browser, events = run(go())
    assert len(browser.executed) == 1
    res = next(e for e in events if e["type"] == "approval_result")
    assert res["approved"] is True and res["by"] == "voice"
    ts = types(events)
    assert ts.index("needs_approval") < ts.index("approval_result")
    assert finished(events)["outcome"] == "done"


def test_a_no_skips_the_step_and_tells_the_model():
    async def go():
        runner, browser, bus, events, sp = make([Proposal([click()]), Proposal(text="Okay.")])
        browser.page.element_probe = {"text": "Buy now", "form": "", "tag": "button"}
        await runner.start("buy it")
        await until(lambda: bus.state.pending_approval is not None)
        await runner.cancel(by="dashboard")
        await drain(runner)
        return browser, events, sp

    browser, events, sp = run(go())
    assert browser.executed == []
    assert sp.seen[0][0].error and "said no" in sp.seen[0][0].error
    assert any(e["type"] == "step" and e["status"] == "failed" and "Skipped" in e["summary"] for e in events)


def test_two_noes_end_the_task_as_cancelled():
    async def go():
        runner, browser, bus, events, _ = make([Proposal([click()]), Proposal([click()]), Proposal(text="x")])
        browser.page.element_probe = {"text": "Delete", "form": "", "tag": "button"}
        await runner.start("delete things")
        for _ in range(2):
            await until(lambda: bus.state.pending_approval is not None)
            await runner.cancel()
            await asyncio.sleep(0.05)
        await drain(runner)
        return events

    assert finished(run(go()))["outcome"] == "cancelled"


def test_no_answer_in_time_counts_as_a_no(monkeypatch):
    monkeypatch.setenv("APPROVAL_TIMEOUT_S", "0")

    async def go():
        runner, browser, bus, events, _ = make([Proposal([click()]), Proposal(text="ok")])
        browser.page.element_probe = {"text": "Join", "form": "", "tag": "button"}
        await runner.start("join")
        await drain(runner)
        return browser, events

    browser, events = run(go())
    assert browser.executed == []
    assert next(e for e in events if e["type"] == "approval_result")["by"] == "timeout"


def test_confirm_with_nothing_pending_does_nothing():
    runner, *_ = make([])
    assert run(runner.confirm()) is False and run(runner.cancel()) is False


# ------------------------------------------------------------------ safety stops
def test_a_password_page_blocks_before_anything_runs():
    async def go():
        runner, browser, bus, events, _ = make([Proposal([click()])])
        browser.page.page_probe = {"password": True, "card": False}
        await runner.start("log in")
        await drain(runner)
        return browser, events, bus

    browser, events, bus = run(go())
    assert browser.executed == []
    blocked = next(e for e in events if e["type"] == "blocked")
    assert blocked["reason"].startswith("This page asks for a password")
    assert finished(events)["outcome"] == "blocked"
    assert bus.state.blocked is not None


def test_landing_on_a_payment_page_blocks_afterwards():
    async def go():
        runner, browser, bus, events, _ = make([Proposal([click()]), Proposal(text="never reached")])
        browser.land_on = "https://www.apple.com/shop/checkout"
        await runner.start("buy an iphone")
        await drain(runner)
        return events

    events = run(go())
    assert any(e["type"] == "blocked" and "payment page" in e["reason"] for e in events)
    assert finished(events)["outcome"] == "blocked"


def test_a_site_off_the_list_is_blocked():
    async def go():
        runner, browser, bus, events, _ = make([Proposal([nav("https://shady.example")])])
        await runner.start("go there")
        await drain(runner)
        return browser, events

    browser, events = run(go())
    assert browser.executed == [] and finished(events)["outcome"] == "blocked"


# ------------------------------------------------------------------ stop, limits, recovery
def test_stop_cancels_a_waiting_task_within_a_second():
    async def go():
        runner, browser, bus, events, _ = make([Proposal([click()])])
        browser.page.element_probe = {"text": "Join", "form": "", "tag": "button"}
        await runner.start("join")
        await until(lambda: bus.state.pending_approval is not None)
        t0 = asyncio.get_event_loop().time()
        await runner.stop()
        took = asyncio.get_event_loop().time() - t0
        await asyncio.sleep(0.02)
        return took, events, runner

    took, events, runner = run(go())
    assert took < 1.0 and not runner.running
    assert finished(events)["outcome"] == "cancelled"


def test_stop_when_idle_is_harmless():
    runner, *_ = make([])
    run(runner.stop())


class Slow:
    async def start(self, goal, png):
        await asyncio.sleep(5)
        return Proposal(text="late")

    async def respond(self, results):
        return Proposal(text="late")


def test_a_task_that_takes_too_long_times_out(monkeypatch):
    monkeypatch.setenv("MAX_TASK_SECONDS", "1")

    async def go():
        runner, browser, bus, events, _ = make([], provider=Slow())
        await runner.start("slow")
        await drain(runner)
        return events

    fin = finished(run(go()))
    assert fin["outcome"] == "timeout" and "too long" in fin["summary"]


def test_step_limit_stops_a_runaway_loop(monkeypatch):
    monkeypatch.setenv("MAX_TASK_STEPS", "3")

    class Forever:
        async def start(self, goal, png):
            return Proposal([Action("wait", name="wait_5_seconds")])

        async def respond(self, results):
            return Proposal([Action("wait", name="wait_5_seconds")])

    async def go():
        runner, browser, bus, events, _ = make([], provider=Forever())
        await runner.start("loop")
        await drain(runner)
        return browser, events

    browser, events = run(go())
    assert len(browser.executed) == 3 and finished(events)["outcome"] == "failed"


def test_a_failing_action_recovers_then_gives_up_after_three():
    async def go():
        browser = FakeBrowser()
        browser.fail_next = 99
        runner, _, bus, events, _ = make([Proposal([click()]), Proposal([click()]), Proposal([click()]),
                                          Proposal(text="unreached")], browser=browser)
        await runner.start("click")
        await drain(runner)
        return events

    events = run(go())
    fails = [e for e in events if e["type"] == "step" and e["status"] == "failed"]
    assert len(fails) == 3 and "trying another way" in fails[0]["summary"]
    assert finished(events)["outcome"] == "failed"


def test_one_failure_then_success_carries_on():
    async def go():
        browser = FakeBrowser()
        browser.fail_next = 1
        runner, _, bus, events, sp = make([Proposal([click()]), Proposal([click()]), Proposal(text="Done!")], browser=browser)
        await runner.start("click")
        await drain(runner)
        return events, sp

    events, sp = run(go())
    assert finished(events)["outcome"] == "done"
    assert sp.seen[0][0].error == "no such element"


def test_a_second_task_is_refused_while_one_runs():
    async def go():
        runner, *_ = make([], provider=Slow())
        await runner.start("one")
        with pytest.raises(TaskBusy):
            await runner.start("two")
        await runner.stop()

    run(go())


def test_empty_goal_is_rejected():
    runner, *_ = make([])
    with pytest.raises(ValueError):
        run(runner.start("   "))


def test_model_failure_is_reported_kindly_not_crashed():
    class Broken:
        async def start(self, goal, png):
            raise ProviderError("no key")

        async def respond(self, results):
            raise AssertionError

    async def go():
        runner, browser, bus, events, _ = make([], provider=Broken())
        await runner.start("x")
        await drain(runner)
        return events

    events = run(go())
    assert any(e["type"] == "error" and e["where"] == "model" for e in events)
    fin = finished(events)
    assert fin["outcome"] == "failed" and "family member" in fin["summary"]


def test_reset_stops_clears_and_returns_to_start():
    async def go():
        runner, browser, bus, events, _ = make([], provider=Slow())
        await runner.start("slow")
        await runner.reset()
        await asyncio.sleep(0.02)
        return runner, browser, bus, events

    runner, browser, bus, events = run(go())
    assert not runner.running and browser.resets == 1
    assert types(events)[-1] == "reset" and bus.state.task is None


def test_multiple_calls_in_one_turn_each_get_a_result():
    async def go():
        runner, browser, bus, events, sp = make([Proposal([click(), click(300, 300)]), Proposal(text="ok")])
        await runner.start("two clicks")
        await drain(runner)
        return browser, sp

    browser, sp = run(go())
    assert len(browser.executed) == 2 and len(sp.seen[0]) == 2
    assert all(isinstance(r, ActionResult) for r in sp.seen[0])


def test_provider_stays_open_through_approval_and_closes_after_task():
    class Client(ScriptedProvider):
        closed = False

        async def close(self):
            self.closed = True

        async def respond(self, results):
            assert not self.closed
            return await super().respond(results)

    async def go():
        client = Client([Proposal([click()]), Proposal(text='Done.')])
        runner, browser, bus, events, _ = make([], provider=client)
        browser.page.element_probe = {'text': 'Join Meeting', 'form': '', 'tag': 'button'}
        await runner.start('join the meeting')
        await until(lambda: bus.state.pending_approval is not None)
        await runner.confirm()
        await drain(runner)
        assert finished(events)['outcome'] == 'done'
        assert client.closed
    run(go())

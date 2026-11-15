import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types

from app.actions import Action
from app.computer_use import ActionResult, GeminiProvider, ProviderError, make_provider


def run(coro):
    return asyncio.run(coro)


def model_reply(*parts):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=list(parts)))])


def call(name, args, id_="id1"):
    return types.Part(function_call=types.FunctionCall(name=name, args=args, id=id_))


class FakeModels:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    async def generate_content(self, model, contents, config):
        self.requests.append((model, list(contents), config))
        return self.replies.pop(0)


def provider(replies):
    p = GeminiProvider(model="test-model", api_key="not-a-real-key")
    fake = FakeModels(replies)
    p.client = SimpleNamespace(aio=SimpleNamespace(models=fake))
    return p, fake


def test_missing_key_gives_a_clear_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        make_provider()


def test_request_has_the_browser_tool_the_goal_and_the_screenshot():
    p, fake = provider([model_reply(call("click_at", {"x": 10, "y": 20}))])
    proposal = run(p.start("play a video", b"PNGBYTES"))

    model, contents, config = fake.requests[0]
    assert model == "test-model"
    assert config.tools[0].computer_use.environment == types.Environment.ENVIRONMENT_BROWSER
    assert "youtube.com" in config.system_instruction          # the allowlist is in the instructions
    parts = contents[0].parts
    assert parts[0].text == "play a video" and parts[1].inline_data.data == b"PNGBYTES"

    assert not proposal.done
    a = proposal.actions[0]
    assert (a.kind, a.nx, a.ny, a.call_id) == ("click", 10.0, 20.0, "id1")


def test_text_only_reply_means_the_task_is_done():
    p, _ = provider([model_reply(types.Part(text="The video is playing now."))])
    proposal = run(p.start("x", b"png"))
    assert proposal.done and proposal.text == "The video is playing now."


def test_reply_carries_the_new_screenshot_the_url_and_any_acknowledgement():
    p, fake = provider([model_reply(call("click_at", {"x": 1, "y": 1})),
                        model_reply(types.Part(text="Done."))])
    run(p.start("x", b"png0"))
    act = Action("click", nx=1, ny=1, name="click_at", call_id="id1")
    out = run(p.respond([ActionResult(act, "https://www.youtube.com/", b"png1", error=None, acknowledged=True)]))
    assert out.done

    sent = fake.requests[1][1][-1]                              # the last message sent to the model
    fr = sent.parts[0].function_response
    assert fr.name == "click_at" and fr.id == "id1"
    assert fr.response == {"url": "https://www.youtube.com/", "safety_acknowledgement": "true"}
    assert fr.parts[0].inline_data.data == b"png1"


def test_an_error_result_is_reported_to_the_model():
    p, fake = provider([model_reply(call("click_at", {"x": 1, "y": 1})), model_reply(types.Part(text="ok"))])
    run(p.start("x", b"png"))
    act = Action("click", nx=1, ny=1, name="click_at", call_id="id1")
    run(p.respond([ActionResult(act, "u", b"p", error="The person said no.")]))
    assert fake.requests[1][1][-1].parts[0].function_response.response["error"] == "The person said no."


def test_old_screenshots_are_pruned_but_recent_ones_stay():
    replies = [model_reply(call("click_at", {"x": 1, "y": 1}, f"id{i}")) for i in range(7)]
    p, fake = provider(replies)
    run(p.start("x", b"png-first"))
    for i in range(6):
        act = Action("click", nx=1, ny=1, name="click_at", call_id=f"id{i}")
        run(p.respond([ActionResult(act, "u", f"png{i}".encode())]))

    last_request = fake.requests[-1][1]
    images = 0
    for c in last_request:
        for part in c.parts:
            fr = part.function_response
            if (fr and fr.parts) or part.inline_data:
                images += 1
    assert images <= GeminiProvider.KEEP_SCREENSHOTS
    assert last_request[0].parts[0].text == "x"                  # the goal itself is never dropped


def test_a_flaky_network_is_retried_then_reported(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.computer_use.asyncio.sleep", no_sleep)

    class Flaky:
        calls = 0

        async def generate_content(self, **kw):
            Flaky.calls += 1
            raise RuntimeError("503")

    p = GeminiProvider(model="m", api_key="k")
    p.client = SimpleNamespace(aio=SimpleNamespace(models=Flaky()))
    with pytest.raises(ProviderError, match="could not be reached"):
        run(p.start("x", b"png"))
    assert Flaky.calls == 3

import asyncio

from app import safety
from app.actions import Action


class FakePage:
    """Stands in for a Playwright page: only `url` and `evaluate` are used by the guard."""

    def __init__(self, url="https://www.youtube.com/", page=None, element=None, boom=False):
        self.url = url
        self.page_probe = page or {"password": False, "card": False}
        self.element_probe = element or {"text": "", "form": "", "tag": "div"}
        self.boom = boom

    async def evaluate(self, js, arg=None):
        if self.boom:
            raise RuntimeError("Execution context was destroyed")
        return self.page_probe if js == safety.PAGE_PROBE_JS else self.element_probe


def run(coro):
    return asyncio.run(coro)


def click(x=500, y=500, **kw):
    return Action("click", nx=x, ny=y, name="click_at", **kw)


# ---- rule 1: allowlist ----
def test_allowlist_matches_registered_domain_and_subdomains():
    assert safety.host_allowed("https://www.youtube.com/watch?v=1")
    assert safety.host_allowed("https://meet.google.com/abc")
    assert safety.host_allowed("https://us02web.zoom.us/j/123")
    assert not safety.host_allowed("https://evil-youtube.com/")
    assert not safety.host_allowed("https://youtube.com.evil.io/")
    assert not safety.host_allowed("file:///C:/secret.txt")


def test_blank_start_page_and_localhost_are_fine():
    assert safety.host_allowed("about:blank")
    assert safety.host_allowed("http://localhost:8000/static/start.html")


def test_current_page_off_the_list_is_blocked():
    v = run(safety.check(click(), FakePage(url="https://shady.example/")))
    assert v.kind == "block" and "safe websites" in v.reason


def test_navigating_off_the_list_is_blocked():
    v = run(safety.check(Action("navigate", url="https://shady.example/"), FakePage()))
    assert v.kind == "block"


def test_navigating_to_an_allowed_site_is_fine():
    assert run(safety.check(Action("navigate", url="youtube.com"), FakePage())).kind == "allow"


# ---- rule 2: passwords, cards, payment pages ----
def test_password_page_is_blocked_in_plain_words():
    v = run(safety.check(click(), FakePage(page={"password": True, "card": False})))
    assert v.kind == "block" and v.reason.startswith("This page asks for a password")


def test_card_fields_are_blocked():
    v = run(safety.check(click(), FakePage(page={"password": False, "card": True})))
    assert v.kind == "block" and "card details" in v.reason


def test_checkout_style_urls_are_blocked():
    for path in ("/shop/checkout", "/payment", "/account/billing", "/pay"):
        v = run(safety.check(click(), FakePage(url="https://www.apple.com" + path)))
        assert v.kind == "block", path


def test_normal_paths_are_not_mistaken_for_payment():
    assert run(safety.check(click(), FakePage(url="https://www.youtube.com/results?search_query=paypal"))).kind == "allow"
    assert run(safety.check(click(), FakePage(url="https://www.apple.com/iphone/"))).kind == "allow"


def test_typing_a_card_number_is_blocked():
    a = Action("type", nx=1, ny=1, text="4111 1111 1111 1111", name="type_text_at")
    assert run(safety.check(a, FakePage())).kind == "block"
    assert run(safety.check(Action("type", nx=1, ny=1, text="dal recipe"), FakePage())).kind == "allow"


# ---- rule 3: ask first ----
def test_joining_asks_first_with_the_button_name():
    v = run(safety.check(click(), FakePage(element={"text": "Join Meeting", "form": "", "tag": "button"})))
    assert v.kind == "ask_first" and v.question == "Shall I press Join Meeting?"


def test_every_ask_word_triggers():
    for word in ("Send", "Submit", "Buy now", "Pay", "Order", "Delete", "Remove", "Download", "Install",
                 "Allow", "Accept all", "Sign up", "Confirm", "Purchase", "Add to Bag", "Add to cart",
                 "Continue to checkout"):
        v = run(safety.check(click(), FakePage(element={"text": word, "form": "", "tag": "button"})))
        assert v.kind == "ask_first", word


def test_play_asks_first_for_the_demo():
    v = run(safety.check(click(), FakePage(element={"text": "Play (k)", "form": "", "tag": "button"})))
    assert v.kind == "ask_first" and "play" in v.question.lower()


def test_ordinary_clicks_are_allowed():
    v = run(safety.check(click(), FakePage(element={"text": "Search", "form": "", "tag": "button"})))
    assert v.kind == "allow"


def test_long_button_text_uses_the_matching_word():
    long = "Click here to join the meeting that everyone else has already joined today"
    v = run(safety.check(click(), FakePage(element={"text": long, "form": "", "tag": "a"})))
    assert v.kind == "ask_first" and len(v.question) < 60


def test_enter_on_a_form_with_a_join_button_asks():
    a = Action("type", nx=1, ny=1, text="Grandma", press_enter=True, name="type_text_at")
    v = run(safety.check(a, FakePage(element={"text": "", "form": "Join now", "tag": "input"})))
    assert v.kind == "ask_first"


def test_enter_in_a_search_box_does_not_ask():
    a = Action("type", nx=1, ny=1, text="dal", press_enter=True, name="type_text_at")
    v = run(safety.check(a, FakePage(element={"text": "", "form": "Search", "tag": "input"})))
    assert v.kind == "allow"


def test_the_enter_key_alone_checks_the_focused_form():
    v = run(safety.check(Action("key", keys="Enter"), FakePage(element={"text": "", "form": "Buy now", "tag": "input"})))
    assert v.kind == "ask_first"


def test_the_models_own_confirmation_request_is_honoured():
    a = click(safety_decision={"decision": "require_confirmation", "explanation": "This looks like a cookie banner."})
    v = run(safety.check(a, FakePage()))
    assert v.kind == "ask_first" and "cookie" in v.reason


# ---- resilience ----
def test_a_page_mid_navigation_does_not_cause_a_false_alarm_or_crash():
    assert run(safety.check(click(), FakePage(boom=True))).kind == "allow"


def test_label_for_gives_a_short_label():
    page = FakePage(element={"text": "Join Meeting", "form": "", "tag": "button"})
    assert run(safety.label_for(click(), page)) == "Join Meeting"
    assert run(safety.label_for(Action("scroll"), page)) == ""


def test_opening_youtube_video_requires_approval_before_navigation():
    v = run(safety.check(Action('navigate',url='https://www.youtube.com/watch?v=demo'), FakePage()))
    assert v.kind == 'ask_first' and 'play' in v.question


def test_model_block_cannot_be_downgraded_to_an_approval():
    v = run(safety.check(Action('navigate',url='https://www.youtube.com/watch?v=demo',
        safety_decision={'decision':'blocked'}), FakePage()))
    assert v.kind == 'block'


def test_typing_can_click_a_risky_button_so_it_also_needs_approval():
    page = FakePage(element={'text':'Join meeting','form':'','tag':'button'})
    assert run(safety.check(Action('type',nx=500,ny=500,text='hello'),page)).kind == 'ask_first'


def test_keyboard_activation_of_video_link_requires_approval():
    page = FakePage(element={'text':'Cooking video','form':'','tag':'a','href':'https://www.youtube.com/watch?v=demo'})
    assert run(safety.check(Action('key',keys='Enter'),page)).kind == 'ask_first'


def test_human_verification_check_stops_the_agent():
    page = FakePage(page={'password':False,'card':False,'challenge':True})
    assert run(safety.check_page(page)).kind == 'block'

from app.actions import Action, normalise_keys, parse_function_call, px


def test_gemini_25_dialect():
    a = parse_function_call("click_at", {"x": 500, "y": 250}, "c1")
    assert (a.kind, a.nx, a.ny, a.call_id) == ("click", 500.0, 250.0, "c1")

    t = parse_function_call("type_text_at", {"x": 10, "y": 20, "text": "dal recipe"})
    assert t.kind == "type" and t.text == "dal recipe" and t.press_enter is True and t.clear is True

    t2 = parse_function_call("type_text_at", {"x": 1, "y": 2, "text": "x", "press_enter": False})
    assert t2.press_enter is False

    assert parse_function_call("navigate", {"url": "https://youtube.com"}).url == "https://youtube.com"
    assert parse_function_call("scroll_document", {"direction": "up"}).direction == "up"
    assert parse_function_call("wait_5_seconds", {}).kind == "wait"
    assert parse_function_call("go_back", {}).kind == "back"
    d = parse_function_call("drag_and_drop", {"x": 1, "y": 2, "destination_x": 3, "destination_y": 4})
    assert (d.kind, d.end_nx, d.end_ny) == ("drag", 3.0, 4.0)


def test_newer_dialect_maps_to_the_same_actions():
    assert parse_function_call("click", {"x": 5, "y": 6}).kind == "click"
    assert parse_function_call("type", {"x": 5, "y": 6, "text": "hi", "press_enter": True}).press_enter is True
    assert parse_function_call("wait", {"seconds": 2}).seconds == 2
    assert parse_function_call("hotkey", {"keys": ["ctrl", "a"]}).keys == "Control+a"


def test_unknown_and_garbage_never_raise():
    assert parse_function_call("do_a_barrel_roll", {"x": "banana"}).kind == "unknown"
    assert parse_function_call("click_at", {"x": "banana"}).nx is None
    assert parse_function_call("", None).kind == "unknown"


def test_model_safety_request_is_kept():
    a = parse_function_call("click_at", {"x": 1, "y": 1,
                            "safety_decision": {"decision": "require_confirmation", "explanation": "Cookie banner"}})
    assert a.safety_decision["decision"] == "require_confirmation"


def test_px_scales_and_clamps():
    assert px(0, 1280) == 0
    assert px(500, 1280) == 640
    assert px(1000, 1280) == 1279 and px(2000, 1280) == 1279 and px(-5, 800) == 0


def test_normalise_keys():
    assert normalise_keys("ctrl+a") == "Control+a"
    assert normalise_keys("Enter") == "Enter"
    assert normalise_keys(["Meta", "C"]) == "Meta+C"
    assert isinstance(Action("noop"), Action)

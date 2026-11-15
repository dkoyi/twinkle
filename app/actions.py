"""The one action vocabulary the whole agent uses.

Models speak different dialects (Gemini 2.5 says `click_at`, newer docs say `click`).
`parse_function_call` maps any of them to an `Action`, so swapping the model never
touches the safety guard or the browser code.

Coordinates from the model are on a 0-1000 grid. `px()` scales them to the viewport.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Kind = Literal[
    "click", "double_click", "right_click", "hover", "type", "scroll", "navigate",
    "key", "wait", "back", "forward", "drag", "noop", "unknown",
]


@dataclass
class Action:
    kind: Kind
    nx: float | None = None          # 0-1000 grid
    ny: float | None = None
    end_nx: float | None = None      # drag destination
    end_ny: float | None = None
    text: str | None = None
    url: str | None = None
    direction: str = "down"
    amount: int = 600                # pixels for scroll
    keys: str | None = None
    press_enter: bool = False
    clear: bool = True
    seconds: float = 2.0
    name: str = ""                   # the model's original function name
    call_id: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    safety_decision: dict | None = None   # the model's own "please confirm" request

    @property
    def has_point(self) -> bool:
        return self.nx is not None and self.ny is not None


def px(n: float, size: int) -> int:
    """0-1000 grid -> pixels, clamped inside the page."""
    return max(0, min(size - 1, int(float(n) / 1000.0 * size)))


def _num(args: dict, *names: str) -> float | None:
    for n in names:
        if n in args and args[n] is not None:
            try:
                return float(args[n])
            except (TypeError, ValueError):
                return None
    return None


def _flag(args: dict, name: str, default: bool) -> bool:
    v = args.get(name, default)
    return v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "yes")


_KEY_NAMES = {"ctrl": "Control", "cmd": "Meta", "command": "Meta", "esc": "Escape", "return": "Enter",
              "del": "Delete", "pgdn": "PageDown", "pgup": "PageUp", "arrowdown": "ArrowDown"}


def normalise_keys(keys: Any) -> str:
    """'ctrl+a', ['Control','A'], 'ENTER' -> Playwright style 'Control+A'."""
    if isinstance(keys, (list, tuple)):
        keys = "+".join(str(k) for k in keys)
    parts = [p.strip() for p in str(keys).split("+") if p.strip()]
    return "+".join(_KEY_NAMES.get(p.lower(), p if len(p) > 1 else p) for p in parts)


def parse_function_call(name: str, args: dict | None, call_id: str | None = None) -> Action:
    """Map a model function call (any known dialect) to an Action. Never raises."""
    args = dict(args or {})
    n = (name or "").lower()
    base = dict(name=name, call_id=call_id, args=args, safety_decision=args.get("safety_decision"))
    x = _num(args, "x", "start_x")
    y = _num(args, "y", "start_y")

    if n in ("click_at", "click", "left_click"):
        return Action("click", nx=x, ny=y, **base)
    if n in ("double_click", "triple_click"):
        return Action("double_click", nx=x, ny=y, **base)
    if n in ("right_click", "middle_click"):
        return Action("right_click", nx=x, ny=y, **base)
    if n in ("hover_at", "move", "mouse_move", "move_mouse"):
        return Action("hover", nx=x, ny=y, **base)
    if n in ("type_text_at", "type", "type_text"):
        return Action("type", nx=x, ny=y, text=str(args.get("text", "")),
                      press_enter=_flag(args, "press_enter", n == "type_text_at"),
                      clear=_flag(args, "clear_before_typing", True), **base)
    if n in ("scroll_document", "scroll_at", "scroll"):
        amount = _num(args, "magnitude", "magnitude_in_pixels", "amount")
        return Action("scroll", nx=x, ny=y, direction=str(args.get("direction", "down")).lower(),
                      amount=int(amount) if amount else 600, **base)
    if n in ("navigate", "open_url", "goto"):
        return Action("navigate", url=str(args.get("url", "")), **base)
    if n == "search":
        return Action("navigate", url="https://www.google.com", **base)
    if n in ("key_combination", "press_key", "hotkey", "key", "keypress"):
        return Action("key", keys=normalise_keys(args.get("keys", args.get("key", ""))), **base)
    if n in ("wait_5_seconds", "wait", "sleep"):
        return Action("wait", seconds=float(_num(args, "seconds") or 5.0), **base)
    if n in ("go_back", "back"):
        return Action("back", **base)
    if n in ("go_forward", "forward"):
        return Action("forward", **base)
    if n == "drag_and_drop":
        return Action("drag", nx=x, ny=y, end_nx=_num(args, "destination_x", "end_x"),
                      end_ny=_num(args, "destination_y", "end_y"), **base)
    if n in ("open_web_browser", "take_screenshot", "screenshot"):
        return Action("noop", **base)
    return Action("unknown", **base)

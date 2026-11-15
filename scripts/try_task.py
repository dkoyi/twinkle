"""Run ONE task from the terminal: no phone, no dashboard needed.

    python scripts/try_task.py "Go to YouTube and play a Ranveer Brar dal recipe video"
    python scripts/try_task.py --demo            # no API key needed: a scripted browser check

A real browser window opens so you can watch it work. Every event is printed.
When TechTwin asks first ("Shall I press Join?") you answer y or n right here.
Press Ctrl+C at any time to stop.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.actions import Action  # noqa: E402
from app.browser import Browser  # noqa: E402
from app.computer_use import Proposal, ScriptedProvider, make_provider  # noqa: E402
from app.events import bus  # noqa: E402
from app.task_runner import TaskBusy, TaskRunner  # noqa: E402

RESET, BOLD, DIM, RED, YEL, GRN = "\033[0m", "\033[1m", "\033[2m", "\033[31m", "\033[33m", "\033[32m"


def demo_provider() -> ScriptedProvider:
    """A fixed little script, so the browser, safety guard and loop can be checked with no model."""
    return ScriptedProvider([
        Proposal([Action("navigate", url="https://www.google.com", name="navigate")]),
        Proposal([Action("scroll", direction="down", name="scroll_document")]),
        Proposal(text="I opened the search page and looked around. That is all for this test."),
    ])


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("goal", nargs="?", help="what you want done, in plain words")
    ap.add_argument("--demo", action="store_true", help="scripted run, no API key needed")
    args = ap.parse_args()
    if not args.goal and not args.demo:
        ap.error("give a goal in quotes, or use --demo")

    browser = Browser()
    runner = TaskRunner(browser, provider_factory=demo_provider if args.demo else make_provider)
    outcome: dict = {}
    done = asyncio.Event()

    async def show(ev: dict) -> None:
        t = ev["type"]
        if t == "task_started":
            print(f"{BOLD}Goal:{RESET} {ev['goal']}")
        elif t == "step":
            color = {"done": GRN, "failed": RED}.get(ev["status"], DIM)
            print(f"  {color}[{ev['n']}] {ev['status']:<7}{RESET} {ev['summary']}")
        elif t == "needs_approval":
            print(f"\n{YEL}{BOLD}TechTwin asks:{RESET} {ev['question']}")
            asyncio.create_task(ask_in_terminal())
        elif t == "approval_result":
            print(f"  {YEL}answer: {'yes' if ev['approved'] else 'no'} (by {ev['by']}){RESET}")
        elif t == "blocked":
            print(f"\n{RED}{BOLD}STOPPED:{RESET} {ev['reason']}")
        elif t == "error":
            print(f"  {RED}error ({ev['where']}): {ev['message']}{RESET}")
        elif t == "task_finished":
            outcome.update(ev)
            print(f"\n{BOLD}Finished:{RESET} {ev['outcome']} in {ev['duration_s']}s, {ev['steps']} steps")
            print(f"{BOLD}TechTwin says:{RESET} {ev['summary']}")
            done.set()

    async def ask_in_terminal() -> None:
        answer = (await asyncio.to_thread(input, "  Shall it go ahead? [y/n] ")).strip().lower()
        if answer.startswith("y"):
            await runner.confirm(by="dashboard")
        else:
            await runner.cancel(by="dashboard")

    bus.subscribe(show)
    print("Opening the browser...")
    await browser.start()
    try:
        await runner.start(args.goal or "Look at the search page")
        await done.wait()
    except TaskBusy as exc:
        print(exc)
    except KeyboardInterrupt:
        pass
    finally:
        await runner.stop()
        await asyncio.sleep(0.3)
        await browser.stop()
    return 0 if outcome.get("outcome") == "done" else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)

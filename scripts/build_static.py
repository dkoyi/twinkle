"""Build a static, deployable copy of the front end (for Vercel or any static host).

    python scripts/build_static.py            # the committed UI (git HEAD): Maulik's phone page + dashboard
    python scripts/build_static.py --working  # the same pages as they are on disk now (uncommitted changes too)
    python scripts/build_static.py --new      # the new single-page app in static/app (local, uncommitted work)

Writes deploy/techtwin/. Only front-end files go in: no Python, no .env, no logs.

Default build takes the files straight from git HEAD (`git archive`), so uncommitted work can never
leak into a deploy.
  /          the phone mockup page (voice_demo/)      /talk   same page
  /dashboard the dashboard in practice mode (scripted call, no backend needed)

A static host has no backend, no WebSocket and no laptop helper, so on it the dashboard plays
its practice call and the phone page can show its screens but cannot place a real call.
The real product (voice, laptop control) runs locally: see docs/FRONTEND.md.
"""
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy" / "techtwin"


def clear_out():
    if OUT.exists():  # clear the old build but keep .vercel (the link to the Vercel project)
        for child in OUT.iterdir():
            if child.name == ".vercel":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)


def build_committed():
    """Maulik's phone page and the original dashboard, exactly as committed."""
    if "--working" in sys.argv:  # what is on disk now, uncommitted changes included
        skip = shutil.ignore_patterns("__pycache__", "*.pyc")
        shutil.copytree(ROOT / "static", OUT / "static", ignore=skip)
        shutil.copytree(ROOT / "voice_demo", OUT / "voice-demo", ignore=skip)
    else:
        data = subprocess.run(["git", "archive", "--format=tar", "HEAD", "static", "voice_demo"],
                              cwd=ROOT, check=True, capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            tar.extractall(OUT, filter="data")
        # The phone page loads /voice-demo/... (with a hyphen); the folder in the repo uses an underscore.
        (OUT / "voice_demo").rename(OUT / "voice-demo")
    # A static host has no voice server: the phone runs its practice call instead of dialling.
    phone = OUT / "static" / "phone.html"
    if phone.exists():
        html = phone.read_text(encoding="utf-8")
        phone.write_text(html.replace("<head>", "<head>\n<script>window.TT_NO_WS = true;</script>", 1), encoding="utf-8")
    return VERCEL_ROUTES


# Keep in step with vercel.json at the repo root (that copy is what Vercel's Git builds read).
VERCEL_ROUTES = {
    "rewrites": [{"source": "/", "destination": "/static/phone.html"},
                 {"source": "/talk", "destination": "/static/phone.html"},
                 {"source": "/help", "destination": "/static/help.html"},
                 {"source": "/classic", "destination": "/voice-demo/index.html"}],
    "redirects": [{"source": "/dashboard", "destination": "/static/dashboard.html?demo=1", "permanent": False},
                  {"source": "/family", "destination": "/static/family.html?demo=1", "permanent": False}],
}


def build_new():
    shutil.copytree(ROOT / "static" / "app", OUT / "static" / "app", ignore=shutil.ignore_patterns("*.part.js"))
    shutil.copytree(ROOT / "static" / "fonts", OUT / "static" / "fonts")
    page = (ROOT / "static" / "app" / "index.html").read_text(encoding="utf-8")
    marker = '<script src="/static/app/twinkle.js"></script>'
    assert marker in page, "index.html changed: update build_static.py"
    page = page.replace(marker, "<script>window.TT_FORCE_DEMO='dal';</script>\n" + marker)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    return {"cleanUrls": True,
            "rewrites": [{"source": "/dashboard", "destination": "/"},
                         {"source": "/talk", "destination": "/"},
                         {"source": "/family", "destination": "/"}]}


def main():
    clear_out()
    config = build_new() if "--new" in sys.argv else build_committed()
    (OUT / "vercel.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    files = sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file() and ".vercel" not in p.parts)
    print(f"Built {OUT}\n  " + "\n  ".join(files))


if __name__ == "__main__":
    main()

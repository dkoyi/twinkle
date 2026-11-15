import os

# Tests never open a real browser or call a real model.
os.environ["BROWSER_AUTOSTART"] = "false"
os.environ.setdefault("ALLOWED_DOMAINS", "youtube.com,google.com,zoom.us,meet.google.com,cvs.com,apple.com")
os.environ.setdefault("ASK_FIRST_EXTRA", "play")
os.environ["LOG_EVENTS"] = "false"

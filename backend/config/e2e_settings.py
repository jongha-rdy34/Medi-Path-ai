"""Settings for the Playwright E2E run (frontend/e2e): file SQLite, stub AI clients.

External APIs (Gemini, ml-service) are replaced by the deterministic stubs in
triage/clients.py; real Gemini latency is measured separately (T30).
"""

import os

from config.settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("E2E_DB", "/tmp/medipath-e2e.sqlite3"),
    }
}
TRIAGE_CLIENTS = "stub"
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

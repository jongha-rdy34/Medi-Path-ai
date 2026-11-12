"""Test settings: in-memory SQLite so pytest needs no PostgreSQL."""

from config.settings import *

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
TRIAGE_CLIENTS = "stub"  # deterministic stubs; HTTP clients are tested against a local server

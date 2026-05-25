import os

# These must be set before `hotel_prj.settings` imports.
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["DEBUG"] = "True"
os.environ["ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"
os.environ["AXES_ENABLED"] = "False"


def pytest_configure(config):
    # By now Django settings have loaded (settings.py calls load_dotenv() which
    # re-populates DATABASE_URL from .env). Override DATABASES so tests use a
    # disposable on-disk SQLite file. Disable django-axes for the same reason.
    from django.conf import settings

    settings.AXES_ENABLED = False
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

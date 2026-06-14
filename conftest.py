import os

# These must be set before `hotel_prj.settings` imports.
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["DEBUG"] = "True"
os.environ["ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"
os.environ["AXES_ENABLED"] = "False"


def pytest_configure(config):
    from django.conf import settings

    settings.AXES_ENABLED = False
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }


import pytest


@pytest.fixture(autouse=True)
def _seed_plans(db):
    from django.core.management import call_command
    call_command("seed_plans", verbosity=0)

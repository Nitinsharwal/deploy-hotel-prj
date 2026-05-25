from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # Import signal handlers so they're connected at app startup.
        # Local import avoids circular references during settings loading.
        from . import signals  # noqa: F401

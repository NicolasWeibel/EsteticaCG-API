from django.apps import AppConfig


class WaxingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.waxing"
    verbose_name = "Waxing"

    def ready(self):
        from . import signals  # noqa: F401

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    verbose_name = "Catalog"

    def ready(self) -> None:
        # Registrar señales (auto-purga de incompatibilidades)
        from . import signals  # noqa

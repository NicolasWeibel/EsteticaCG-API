from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"  # <- IMPORTANTE: con el prefijo "apps."
    verbose_name = "Catalog"

# ==========================================
# apps/authcodes/apps.py
# ==========================================
from django.apps import AppConfig


class AuthcodesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authcodes"
    label = "authcodes"  # Por qué: etiqueta estable para migraciones

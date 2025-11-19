# apps/users/apps.py
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"  # ruta del paquete
    label = "users"  # etiqueta estable para AUTH_USER_MODEL y FKs

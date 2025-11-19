# ===========================================
# apps/users/management/commands/grant_admin_access.py
# ===========================================
from __future__ import annotations

from typing import Iterable, List, Set
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.conf import settings

# Por qué: evitar dar superuser; asignar solo lo necesario, agrupado en un Group.
# Uso:
#   python manage.py grant_admin_access --email alice@example.com
#   # Acceso básico (is_staff + view/change) a todas las apps locales "apps.*"
#
#   python manage.py grant_admin_access --email alice@example.com --perms view,change,add --apps catalog,authcodes
#   # Solo apps indicadas y acciones pedidas
#
#   python manage.py grant_admin_access --email alice@example.com --group Backoffice --perms view
#   # Crea/usa el grupo "Backoffice" y da solo permisos de lectura
#
#   python manage.py grant_admin_access --email alice@example.com --revoke
#   # Quita el usuario del grupo y (opcional) revoca is_staff si no está en otros grupos de admin

LOCAL_APPS_PREFIX = "apps."


class Command(BaseCommand):
    help = (
        "Concede acceso al Django admin sin superuser: "
        "marca is_staff y asigna permisos via Group de forma idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email del usuario.")
        parser.add_argument(
            "--group",
            default="Backoffice",
            help='Nombre del grupo a crear/usar (default: "Backoffice").',
        )
        parser.add_argument(
            "--apps",
            default="",
            help="Lista separada por comas de apps (labels) p. ej.: users,catalog,authcodes. "
            "Si se omite, se toman todas las apps locales que empiezan con 'apps.'.",
        )
        parser.add_argument(
            "--perms",
            default="view,change",
            help="Acciones a otorgar: subset de view,change,add,delete (default: view,change).",
        )
        parser.add_argument(
            "--no_staff",
            action="store_true",
            help="No marcar is_staff (por defecto sí se marca).",
        )
        parser.add_argument(
            "--revoke",
            action="store_true",
            help="Quitar usuario del grupo y, si corresponde, remover is_staff.",
        )

    def handle(self, *args, **opts):
        email: str = opts["email"].strip().lower()
        group_name: str = opts["group"]
        revoke: bool = bool(opts["revoke"])
        set_staff: bool = not bool(opts["no_staff"])

        actions: List[str] = self._parse_actions(opts["perms"])
        app_labels: List[str] = self._parse_apps(opts["apps"])

        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as e:
            raise CommandError(f"Usuario no encontrado: {email}") from e

        if revoke:
            self._revoke(user, group_name)
            self.stdout.write(self.style.SUCCESS("Acceso revocado (si aplicaba)."))
            return

        group = self._ensure_group(group_name)

        if not app_labels:
            app_labels = self._local_app_labels()

        perms = self._collect_perms(app_labels, actions)
        if not perms:
            raise CommandError(
                "No se resolvieron permisos para las apps/acciones indicadas."
            )

        group.permissions.set(perms | set(group.permissions.all()))
        group.save()

        if group not in user.groups.all():
            user.groups.add(group)

        if set_staff and not user.is_staff:
            user.is_staff = True  # Por qué: requisito para acceder al admin
            user.save(update_fields=["is_staff"])

        self.stdout.write(
            self.style.SUCCESS(
                f"OK. Usuario={user.email} is_staff={user.is_staff}. "
                f"Grupo='{group.name}' con {len(perms)} permisos aplicados."
            )
        )

    # ---------- helpers ----------

    def _parse_actions(self, s: str) -> List[str]:
        allowed = {"view", "change", "add", "delete"}
        parts = [p.strip().lower() for p in s.split(",") if p.strip()]
        bad = [p for p in parts if p not in allowed]
        if bad:
            raise CommandError(
                f"Acciones inválidas: {bad}. Permitidas: {sorted(allowed)}"
            )
        return parts or ["view", "change"]

    def _parse_apps(self, s: str) -> List[str]:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return parts

    def _local_app_labels(self) -> List[str]:
        # Por qué: solo apps del proyecto (prefijo apps.)
        labels = []
        for app_config in apps.get_app_configs():
            if app_config.name.startswith(LOCAL_APPS_PREFIX):
                labels.append(app_config.label)
        return labels

    def _ensure_group(self, name: str) -> Group:
        group, _ = Group.objects.get_or_create(name=name)
        return group

    def _collect_perms(
        self, app_labels: Iterable[str], actions: Iterable[str]
    ) -> Set[Permission]:
        perms: Set[Permission] = set()
        for label in app_labels:
            try:
                app_config = apps.get_app_config(label)
            except LookupError:
                raise CommandError(f"App label no encontrada: '{label}'")
            for model in app_config.get_models():
                ct = ContentType.objects.get_for_model(model)
                codenames = [f"{a}_{model._meta.model_name}" for a in actions]
                qs = Permission.objects.filter(content_type=ct, codename__in=codenames)
                perms.update(qs)
        return perms

    def _revoke(self, user, group_name: str) -> None:
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            group = None
        if group and group in user.groups.all():
            user.groups.remove(group)
        # Si el usuario no pertenece a ningún grupo con permisos de admin, se puede desmarcar is_staff.
        # Por qué: evitar que quede acceso al /admin sin permisos asignados.
        if user.is_staff:
            still_adminish = user.groups.filter(permissions__isnull=False).exists()
            if not still_adminish:
                user.is_staff = False
                user.save(update_fields=["is_staff"])

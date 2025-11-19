# ===========================================
# apps/users/management/commands/add_google_app.py
# (versión idempotente + anti-duplicados)
# ===========================================
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.contrib.sites.models import Site
import os


class Command(BaseCommand):
    help = "Crea/actualiza la SocialApp de Google (allauth) y garantiza una única por Site."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        from allauth.socialaccount.models import SocialApp  # type: ignore

        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        if not client_id or not secret:
            self.stderr.write("Faltan GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET.")
            return

        site_id = int(os.environ.get("SITE_ID", getattr(settings, "SITE_ID", 1)))
        site, _ = Site.objects.get_or_create(
            id=site_id, defaults={"domain": "localhost", "name": "Local"}
        )

        # Crear/obtener principal por provider
        app, created = SocialApp.objects.get_or_create(
            provider="google",
            name="Google",
            defaults={"client_id": client_id, "secret": secret, "key": ""},
        )

        # Sincronizar credenciales si cambiaron
        changed = False
        if app.client_id != client_id:
            app.client_id = client_id
            changed = True
        if app.secret != secret:
            app.secret = secret
            changed = True
        if app.key != "":
            app.key = ""
            changed = True
        if changed:
            app.save()

        # Asociar SOLO el site actual
        app.sites.set([site])

        # Quitar duplicadas del mismo provider para este site y borrar huérfanas
        duplicates = (
            SocialApp.objects.filter(provider="google").exclude(id=app.id).distinct()
        )
        removed = 0
        deleted = 0
        for dup in duplicates:
            if site in dup.sites.all():
                dup.sites.remove(site)  # Por qué: allauth selecciona por Site
                removed += 1
            if dup.sites.count() == 0:
                dup.delete()
                deleted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"SocialApp Google lista (id={app.id}). Removidas del site: {removed}. "
                f"Eliminadas sin sites: {deleted}."
            )
        )

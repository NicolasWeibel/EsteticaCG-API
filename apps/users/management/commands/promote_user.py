# apps/users/management/commands/promote_user.py
from django.core.management.base import BaseCommand, CommandError
from apps.users.models import User


class Command(BaseCommand):
    help = "Promueve un usuario a staff y/o superuser por email"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--staff", action="store_true")
        parser.add_argument("--superuser", action="store_true")

    def handle(self, *args, **opts):
        try:
            u = User.objects.get(email=opts["email"])
        except User.DoesNotExist as e:
            raise CommandError(f"Usuario no encontrado: {opts['email']}") from e
        changed = False
        if opts["staff"] and not u.is_staff:
            u.is_staff = True
            changed = True
        if opts["superuser"] and not u.is_superuser:
            u.is_superuser = True
            u.is_staff = True
            changed = True
        if changed:
            u.save()
            self.stdout.write(self.style.SUCCESS("Actualizado"))
        else:
            self.stdout.write("Sin cambios")

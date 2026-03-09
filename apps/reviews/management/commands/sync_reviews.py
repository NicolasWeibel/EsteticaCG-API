from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...models import ManualReview
from ...services import GoogleReviewsError, sync_google_reviews


class Command(BaseCommand):
    help = "Sincroniza reviews en cache (Google) o valida disponibilidad de manual reviews."

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            choices=("google", "manual"),
            default=settings.REVIEWS_PROVIDER,
            help="Provider a sincronizar.",
        )

    def handle(self, *args, **options):
        provider = options["provider"]

        if provider == "manual":
            total = ManualReview.objects.filter(is_active=True).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Provider manual activo. Reviews manuales activas: {total}"
                )
            )
            return

        try:
            result = sync_google_reviews()
        except GoogleReviewsError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync Google completado. Recibidas={result['received']} "
                f"Sincronizadas={result['synced']}"
            )
        )

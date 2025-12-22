from django.core.exceptions import ValidationError
from django.db import models
from .item_base import ItemBase
from .filters import TreatmentType, Objective, IntensityLevel, DurationBucket
from .base import TimeStampedUUIDModel


class Treatment(ItemBase):
    treatment_types = models.ManyToManyField(TreatmentType, blank=True)
    objectives = models.ManyToManyField(Objective, blank=True)
    intensities = models.ManyToManyField(IntensityLevel, blank=True)
    durations = models.ManyToManyField(DurationBucket, blank=True)

    # Un treatment por defecto requiere seleccionar zonas
    requires_zones = models.BooleanField(default=True)


class TreatmentZoneConfig(TimeStampedUUIDModel):
    class BodyPosition(models.TextChoices):
        BOCA_ARRIBA = "boca-arriba", "Boca arriba"
        BOCA_ABAJO = "boca-abajo", "Boca abajo"
        ANY = "any", "Cualquiera"

    treatment = models.ForeignKey(
        Treatment, on_delete=models.CASCADE, related_name="zone_configs"
    )
    zone = models.ForeignKey("Zone", on_delete=models.CASCADE)

    # duración: un solo número (minutos)
    duration = models.PositiveIntegerField()

    # precios a nivel zona:
    price = models.DecimalField(max_digits=10, decimal_places=2)
    promotional_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    body_position = models.CharField(
        max_length=20, choices=BodyPosition.choices, blank=True
    )

    class Meta:
        unique_together = ("treatment", "zone")
        constraints = [
            models.CheckConstraint(
                check=models.Q(duration__gt=0), name="ck_tzc_duration_gt_0"
            ),
            models.CheckConstraint(
                check=models.Q(price__gt=0), name="ck_tzc_price_gt_0"
            ),
            models.CheckConstraint(
                check=(
                    models.Q(promotional_price__isnull=True)
                    | models.Q(promotional_price__gt=0)
                ),
                name="ck_tzc_promo_gt_0_or_null",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(promotional_price__isnull=True)
                    | models.Q(promotional_price__lt=models.F("price"))
                ),
                name="ck_tzc_promo_lt_price",
            ),
        ]
        indexes = [
            models.Index(fields=["treatment", "zone"]),
            models.Index(fields=["zone"]),
        ]

    def clean(self):
        # misma categoría
        if self.zone.category_id != self.treatment.category_id:  # type: ignore[attr-defined]
            raise ValidationError(
                "La zona y el tratamiento deben pertenecer a la misma categoría."
            )
        # promo < price si existe
        if self.promotional_price is not None and self.promotional_price >= self.price:
            raise ValidationError("El precio promocional debe ser menor que el precio.")

    def __str__(self) -> str:
        # Mostrar: "Crio / Glúteos / Boca abajo"
        pos = self.get_body_position_display() or "—"
        try:
            return f"{self.treatment.title} / {self.zone.name} / {pos}"
        except Exception:
            # fallback robusto si faltan relaciones en admin durante edición
            return f"TZC {self.pk}"

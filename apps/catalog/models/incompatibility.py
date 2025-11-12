# apps/catalog/models/incompatibility.py

from django.core.exceptions import ValidationError
from django.db import models
from .base import TimeStampedUUIDModel


def positions_overlap(a: str, b: str) -> bool:
    if a == "any" or b == "any":
        return True
    return a == b


class TreatmentZoneIncompatibility(TimeStampedUUIDModel):
    left_tzc = models.ForeignKey(
        "catalog.TreatmentZoneConfig",  # ⬅️ referencia por string (app_label.ModelName)
        on_delete=models.CASCADE,
        related_name="incompat_left",
    )
    right_tzc = models.ForeignKey(
        "catalog.TreatmentZoneConfig",  # ⬅️ referencia por string
        on_delete=models.CASCADE,
        related_name="incompat_right",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["left_tzc", "right_tzc"], name="uq_tzc_incompat_pair"
            ),
            models.CheckConstraint(
                check=~models.Q(left_tzc=models.F("right_tzc")),
                name="ck_tzc_incompat_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["left_tzc"]),
            models.Index(fields=["right_tzc"]),
        ]

    def clean(self):
        super().clean()
        if (
            self.left_tzc_id
            and self.right_tzc_id
            and self.left_tzc_id > self.right_tzc_id
        ):
            self.left_tzc_id, self.right_tzc_id = self.right_tzc_id, self.left_tzc_id
        if not self.left_tzc_id or not self.right_tzc_id:
            return
        left = self.left_tzc
        right = self.right_tzc
        if left.zone_id == right.zone_id:
            raise ValidationError(
                "No se pueden definir incompatibilidades para la misma zona."
            )
        if left.treatment.category_id != right.treatment.category_id:  # type: ignore[attr-defined]
            raise ValidationError(
                "Ambas configuraciones deben pertenecer a la misma categoría."
            )
        if not positions_overlap(left.body_position, right.body_position):
            raise ValidationError(
                "Las posiciones no solapan: no corresponde incompatibilidad."
            )

    def save(self, *args, **kwargs):
        if (
            self.left_tzc_id
            and self.right_tzc_id
            and self.left_tzc_id > self.right_tzc_id
        ):
            self.left_tzc_id, self.right_tzc_id = self.right_tzc_id, self.left_tzc_id
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.left_tzc} ↔ {self.right_tzc}"

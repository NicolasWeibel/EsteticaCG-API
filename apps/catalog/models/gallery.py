from django.conf import settings
from django.db import models

from .base import TimeStampedUUIDModel


class TreatmentImage(TimeStampedUUIDModel):
    treatment = models.ForeignKey(
        "catalog.Treatment", on_delete=models.CASCADE, related_name="images"
    )
    # CAMBIO: Usamos ImageField
    image = models.ImageField(upload_to="catalog/treatments/", verbose_name="image")
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order"]


class ComboImage(TimeStampedUUIDModel):
    combo = models.ForeignKey(
        "catalog.Combo", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="catalog/combos/", verbose_name="image")
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order"]


class JourneyImage(TimeStampedUUIDModel):
    journey = models.ForeignKey(
        "catalog.Journey", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="catalog/journeys/", verbose_name="image")
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order"]

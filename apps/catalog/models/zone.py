from django.db import models
from django.db.models.functions import Lower
from .base import TimeStampedUUIDModel
from .category import Category


class Zone(TimeStampedUUIDModel):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # evita borrar Cat si hay Zonas
        related_name="zones",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "category", name="uq_zone_name_ci_per_category"
            )
        ]
        indexes = [models.Index(fields=["category", "name"])]

    def __str__(self) -> str:
        return self.name

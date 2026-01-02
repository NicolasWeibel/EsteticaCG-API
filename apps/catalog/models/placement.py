from django.core.exceptions import ValidationError
from django.db import models

from .base import TimeStampedUUIDModel
from .combo import Combo
from .journey import Journey
from .treatment import Treatment


class Placement(TimeStampedUUIDModel):
    slug = models.SlugField(max_length=50, unique=True)
    title = models.CharField(max_length=100)
    max_items = models.PositiveIntegerField(default=40)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["slug"])]

    def __str__(self) -> str:
        return self.title


class PlacementItem(TimeStampedUUIDModel):
    class ItemKind(models.TextChoices):
        TREATMENT = "treatment", "Treatment"
        COMBO = "combo", "Combo"
        JOURNEY = "journey", "Journey"

    placement = models.ForeignKey(
        Placement, on_delete=models.CASCADE, related_name="items"
    )
    item_kind = models.CharField(max_length=20, choices=ItemKind.choices)
    item_id = models.UUIDField()
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        unique_together = ("placement", "item_kind", "item_id")
        indexes = [models.Index(fields=["placement", "order"])]

    def clean(self):
        super().clean()
        if self.item_kind == self.ItemKind.TREATMENT:
            model = Treatment
        elif self.item_kind == self.ItemKind.COMBO:
            model = Combo
        elif self.item_kind == self.ItemKind.JOURNEY:
            model = Journey
        else:
            raise ValidationError("Invalid item kind.")

        if not model.objects.filter(id=self.item_id).exists():
            raise ValidationError("Invalid item.")

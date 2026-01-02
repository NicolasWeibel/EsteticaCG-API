from django.core.exceptions import ValidationError
from django.db import models

from .base import TimeStampedUUIDModel
from .category import Category
from .journey import Journey
from .treatment import Treatment
from .combo import Combo


class ItemOrder(TimeStampedUUIDModel):
    class ContextKind(models.TextChoices):
        CATEGORY = "category", "Category"
        JOURNEY = "journey", "Journey"

    class ItemKind(models.TextChoices):
        TREATMENT = "treatment", "Treatment"
        COMBO = "combo", "Combo"
        JOURNEY = "journey", "Journey"

    context_kind = models.CharField(max_length=20, choices=ContextKind.choices)
    context_id = models.UUIDField()
    item_kind = models.CharField(max_length=20, choices=ItemKind.choices)
    item_id = models.UUIDField()
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        unique_together = ("context_kind", "context_id", "item_kind", "item_id")
        indexes = [
            models.Index(fields=["context_kind", "context_id", "order"]),
            models.Index(fields=["context_kind", "context_id"]),
        ]

    def clean(self):
        super().clean()
        context = self._get_context()
        item = self._get_item()
        self._validate_item_in_context(context, item)

    def _get_context(self):
        if self.context_kind == self.ContextKind.CATEGORY:
            return Category.objects.filter(id=self.context_id).first()
        if self.context_kind == self.ContextKind.JOURNEY:
            return Journey.objects.filter(id=self.context_id).first()
        return None

    def _get_item(self):
        if self.item_kind == self.ItemKind.TREATMENT:
            return Treatment.objects.filter(id=self.item_id).first()
        if self.item_kind == self.ItemKind.COMBO:
            return Combo.objects.filter(id=self.item_id).first()
        if self.item_kind == self.ItemKind.JOURNEY:
            return Journey.objects.filter(id=self.item_id).first()
        return None

    def _validate_item_in_context(self, context, item):
        if context is None:
            raise ValidationError("Invalid context.")
        if item is None:
            raise ValidationError("Invalid item.")

        if self.context_kind == self.ContextKind.CATEGORY:
            if self.item_kind == self.ItemKind.JOURNEY:
                if item.category_id != context.id:
                    raise ValidationError("Journey must belong to the category.")
            else:
                if item.category_id != context.id:
                    raise ValidationError("Item must belong to the category.")
        elif self.context_kind == self.ContextKind.JOURNEY:
            if self.item_kind == self.ItemKind.JOURNEY:
                raise ValidationError("Journeys are not valid items in a journey.")
            if item.journey_id != context.id:
                raise ValidationError("Item must belong to the journey.")

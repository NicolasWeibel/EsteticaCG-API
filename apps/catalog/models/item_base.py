from django.db import models
from .base import TimeStampedUUIDModel
from .category import Category


class ItemBase(TimeStampedUUIDModel):
    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    image = models.URLField(blank=True, null=True)
    modal_title = models.CharField(max_length=200, blank=True)
    modal_description = models.TextField(blank=True)
    modal_image = models.URLField(blank=True, null=True)

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="%(class)ss"
    )
    journey = models.ForeignKey(
        "catalog.Journey",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)ss",  # ✅ Journey.treatments / Journey.combos
    )
    # flags + orden editorial
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["category", "title"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.title

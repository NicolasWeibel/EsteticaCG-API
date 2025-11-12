# apps/catalog/models/journey.py

from django.db import models
from .base import TimeStampedUUIDModel
from .category import Category


class Journey(TimeStampedUUIDModel):
    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.URLField(blank=True, null=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="journeys"
    )
    addons = models.ManyToManyField(
        "catalog.Treatment",
        related_name="addon_in_journeys",
        blank=True,  # ✅ string ref
    )

    def __str__(self):
        return self.title

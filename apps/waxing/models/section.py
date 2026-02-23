from django.db import models

from .base import TimeStampedUUIDModel
from .choices import SortOption


class Section(TimeStampedUUIDModel):
    name = models.CharField(max_length=120, unique=True)
    image = models.ImageField(upload_to="waxing/sections/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    featured_sort = models.CharField(
        max_length=20,
        choices=SortOption.choices,
        default=SortOption.MANUAL,
    )

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

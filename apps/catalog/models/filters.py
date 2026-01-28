from django.db import models
from .base import TimeStampedUUIDModel
from .category import Category


class TreatmentType(TimeStampedUUIDModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Objective(TimeStampedUUIDModel):
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to="objectives/", blank=True, null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="objectives",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name


class IntensityLevel(TimeStampedUUIDModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


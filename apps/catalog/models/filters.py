from django.db import models
from .base import TimeStampedUUIDModel


class TreatmentType(TimeStampedUUIDModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Objective(TimeStampedUUIDModel):
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to="objectives/", blank=True, null=True)

    def __str__(self):
        return self.name


class IntensityLevel(TimeStampedUUIDModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


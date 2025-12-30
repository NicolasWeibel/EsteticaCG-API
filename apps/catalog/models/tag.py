from django.db import models
from .base import TimeStampedUUIDModel


class Tag(TimeStampedUUIDModel):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

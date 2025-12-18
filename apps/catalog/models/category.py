from django.db import models
from django.db.models.functions import Lower
from .base import TimeStampedUUIDModel


class Category(TimeStampedUUIDModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("slug"), name="uq_category_slug_ci")
        ]
        indexes = [models.Index(fields=["slug"])]

    def __str__(self) -> str:
        return self.name

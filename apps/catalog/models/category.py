from django.db import models
from django.db.models.functions import Lower
from .base import TimeStampedUUIDModel


class Category(TimeStampedUUIDModel):
    class JourneyPosition(models.TextChoices):
        FIRST = "FIRST", "First"
        LAST = "LAST", "Last"

    class SortOption(models.TextChoices):
        PRICE_ASC = "price_asc", "Price asc"
        PRICE_DESC = "price_desc", "Price desc"
        AZ = "az", "A-Z"
        ZA = "za", "Z-A"
        NEWEST = "newest", "Newest"
        OLDEST = "oldest", "Oldest"
        MANUAL = "manual", "Manual"

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    include_journeys = models.BooleanField(default=True)
    journey_position = models.CharField(
        max_length=5,
        choices=JourneyPosition.choices,
        default=JourneyPosition.LAST,
    )
    default_sort = models.CharField(
        max_length=20,
        choices=SortOption.choices,
        default=SortOption.PRICE_ASC,
    )
    seo_title = models.CharField(max_length=70, blank=True)
    seo_description = models.CharField(max_length=160, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("slug"), name="uq_category_slug_ci")
        ]
        indexes = [models.Index(fields=["slug"])]

    def __str__(self) -> str:
        return self.name

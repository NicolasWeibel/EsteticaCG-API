from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from .base import TimeStampedUUIDModel
from .category import Category


class ItemBase(TimeStampedUUIDModel):
    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=255, blank=True)
    seo_title = models.CharField(max_length=70, blank=True)
    seo_description = models.CharField(max_length=160, blank=True)
    recommended_description = models.TextField(blank=True)
    benefits_image = models.ImageField(
        upload_to="catalog/items/benefits/",
        blank=True,
        null=True,
    )
    recommended_image = models.ImageField(
        upload_to="catalog/items/recommended/",
        blank=True,
        null=True,
    )

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="%(class)ss"
    )
    journey = models.ForeignKey(
        "catalog.Journey",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)ss",  # ✅ Journey.treatments / Journey.combos
    )
    tags = models.ManyToManyField(
        "catalog.Tag",
        related_name="%(class)ss",
        blank=True,
    )
    benefits = GenericRelation("catalog.ItemBenefit", related_query_name="item")
    recommended_points = GenericRelation(
        "catalog.ItemRecommendedPoint", related_query_name="item"
    )
    faqs = GenericRelation("catalog.ItemFAQ", related_query_name="item")
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

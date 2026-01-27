from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from .base import TimeStampedUUIDModel


class ItemContentBase(TimeStampedUUIDModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["order"]


class ItemBenefit(ItemContentBase):
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True)

    class Meta(ItemContentBase.Meta):
        verbose_name = "Item benefit"
        verbose_name_plural = "Item benefits"
        indexes = [
            models.Index(fields=["content_type", "object_id", "order"], name="catalog_itembenefit_idx")
        ]

    def __str__(self) -> str:
        return self.title


class ItemRecommendedPoint(ItemContentBase):
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True)

    class Meta(ItemContentBase.Meta):
        verbose_name = "Item recommended point"
        verbose_name_plural = "Item recommended points"
        indexes = [
            models.Index(fields=["content_type", "object_id", "order"], name="catalog_itemrpoint_idx")
        ]

    def __str__(self) -> str:
        return self.title


class ItemFAQ(ItemContentBase):
    question = models.CharField(max_length=255)
    answer = models.TextField()

    class Meta(ItemContentBase.Meta):
        verbose_name = "Item FAQ"
        verbose_name_plural = "Item FAQs"
        indexes = [
            models.Index(fields=["content_type", "object_id", "order"], name="catalog_itemfaq_idx")
        ]

    def __str__(self) -> str:
        return self.question

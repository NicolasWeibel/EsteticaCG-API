from django.core.exceptions import ValidationError
from django.db import models

from .base import TimeStampedUUIDModel


class WaxingContent(TimeStampedUUIDModel):
    singleton_key = models.PositiveSmallIntegerField(
        default=1,
        unique=True,
        editable=False,
    )
    title = models.CharField(max_length=255)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    recommendations_intro_text = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="waxing/content/",
        blank=True,
        null=True,
    )
    benefits_image = models.ImageField(
        upload_to="waxing/content/",
        blank=True,
        null=True,
    )
    recommendations_image = models.ImageField(
        upload_to="waxing/content/",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Waxing content"
        verbose_name_plural = "Waxing content"

    def clean(self):
        super().clean()
        if self.singleton_key != 1:
            raise ValidationError("singleton_key invalido para WaxingContent.")

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class BenefitItem(TimeStampedUUIDModel):
    content = models.ForeignKey(
        WaxingContent,
        on_delete=models.CASCADE,
        related_name="benefits",
    )
    title = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "id")
        indexes = [models.Index(fields=("content", "order"))]

    def __str__(self):
        return self.title


class RecommendationItem(TimeStampedUUIDModel):
    content = models.ForeignKey(
        WaxingContent,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    title = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "id")
        indexes = [models.Index(fields=("content", "order"))]

    def __str__(self):
        return self.title


class FaqItem(TimeStampedUUIDModel):
    content = models.ForeignKey(
        WaxingContent,
        on_delete=models.CASCADE,
        related_name="faqs",
    )
    question = models.TextField()
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "id")
        indexes = [models.Index(fields=("content", "order"))]

    def __str__(self):
        return self.question[:80]

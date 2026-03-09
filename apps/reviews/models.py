import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class TimeStampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ManualReview(TimeStampedUUIDModel):
    author_name = models.CharField(max_length=120)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    source_label = models.CharField(max_length=80, default="Testimonio")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ("order", "-created_at")
        indexes = [
            models.Index(fields=("is_active", "order")),
            models.Index(fields=("rating", "is_active")),
        ]

    def __str__(self):
        return f"{self.author_name} ({self.rating})"


class GoogleReviewCache(TimeStampedUUIDModel):
    external_id = models.CharField(max_length=255, unique=True)
    reviewer_name = models.CharField(max_length=255, blank=True)
    reviewer_profile_photo_url = models.URLField(blank=True)
    reviewer_is_anonymous = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    create_time = models.DateTimeField(blank=True, null=True)
    update_time = models.DateTimeField(blank=True, null=True)
    fetched_at = models.DateTimeField(db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    is_hidden = models.BooleanField(default=False)
    hidden_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-update_time", "-create_time", "-fetched_at")
        indexes = [
            models.Index(fields=("is_hidden", "fetched_at")),
            models.Index(fields=("rating", "fetched_at")),
        ]

    def __str__(self):
        reviewer = self.reviewer_name or "Anonimo"
        return f"{reviewer} ({self.rating})"

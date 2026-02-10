from django.db import models
from django.db.models.fields.files import FieldFile
from cloudinary.utils import cloudinary_url

from .base import TimeStampedUUIDModel

class MediaFieldFile(FieldFile):
    @property
    def url(self):
        if not self.name:
            return ""
        media_type = getattr(self.instance, "media_type", None)
        if media_type == "video":
            try:
                url, _ = cloudinary_url(
                    self.name,
                    resource_type="video",
                    secure=True,
                )
                return url
            except Exception:
                pass
        return super().url


class MediaField(models.FileField):
    attr_class = MediaFieldFile

MEDIA_TYPE_IMAGE = "image"
MEDIA_TYPE_VIDEO = "video"
MEDIA_TYPE_CHOICES = (
    (MEDIA_TYPE_IMAGE, "Imagen"),
    (MEDIA_TYPE_VIDEO, "Video"),
)


class TreatmentMedia(TimeStampedUUIDModel):
    treatment = models.ForeignKey(
        "catalog.Treatment", on_delete=models.CASCADE, related_name="media"
    )
    media = MediaField(
        upload_to="catalog/treatments/",
        verbose_name="media",
        max_length=255,
    )
    media_type = models.CharField(
        max_length=10, choices=MEDIA_TYPE_CHOICES, default=MEDIA_TYPE_IMAGE
    )
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order"]


class ComboMedia(TimeStampedUUIDModel):
    combo = models.ForeignKey(
        "catalog.Combo", on_delete=models.CASCADE, related_name="media"
    )
    media = MediaField(
        upload_to="catalog/combos/",
        verbose_name="media",
        max_length=255,
    )
    media_type = models.CharField(
        max_length=10, choices=MEDIA_TYPE_CHOICES, default=MEDIA_TYPE_IMAGE
    )
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order"]


class JourneyMedia(TimeStampedUUIDModel):
    journey = models.ForeignKey(
        "catalog.Journey", on_delete=models.CASCADE, related_name="media"
    )
    media = MediaField(
        upload_to="catalog/journeys/",
        verbose_name="media",
        max_length=255,
    )
    media_type = models.CharField(
        max_length=10, choices=MEDIA_TYPE_CHOICES, default=MEDIA_TYPE_IMAGE
    )
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["order"]

from django.core.exceptions import ValidationError
from django.db import models

from .base import TimeStampedUUIDModel
from .choices import PackPosition, SortOption


class WaxingSettings(TimeStampedUUIDModel):
    singleton_key = models.PositiveSmallIntegerField(
        default=1,
        unique=True,
        editable=False,
    )
    is_enabled = models.BooleanField(default=True)
    public_visible = models.BooleanField(default=True)
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    allow_booking = models.BooleanField(default=True)
    show_prices = models.BooleanField(default=True)
    featured_enabled = models.BooleanField(default=True)
    default_area_sort = models.CharField(
        max_length=20,
        choices=SortOption.choices,
        default=SortOption.MANUAL,
    )
    default_pack_sort = models.CharField(
        max_length=20,
        choices=SortOption.choices,
        default=SortOption.MANUAL,
    )
    default_pack_position = models.CharField(
        max_length=10,
        choices=PackPosition.choices,
        default=PackPosition.FIRST,
    )

    class Meta:
        verbose_name = "Waxing settings"
        verbose_name_plural = "Waxing settings"

    def clean(self):
        super().clean()
        if self.singleton_key != 1:
            raise ValidationError("singleton_key invalido para WaxingSettings.")

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return "Configuracion global de waxing"

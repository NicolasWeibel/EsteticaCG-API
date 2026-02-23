from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from .base import TimeStampedUUIDModel
from .choices import PackPosition, SortOption
from .section import Section


class AreaCategory(TimeStampedUUIDModel):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=120)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="waxing/area_categories/",
        blank=True,
        null=True,
    )
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)
    show_packs = models.BooleanField(default=True)
    area_sort = models.CharField(
        max_length=20,
        choices=SortOption.choices,
        default=SortOption.MANUAL,
    )
    pack_sort = models.CharField(
        max_length=20,
        choices=SortOption.choices,
        default=SortOption.MANUAL,
    )
    pack_position = models.CharField(
        max_length=10,
        choices=PackPosition.choices,
        default=PackPosition.FIRST,
    )

    class Meta:
        ordering = ("order", "name")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "section",
                name="uq_waxing_area_category_name_ci_per_section",
            )
        ]
        indexes = [
            models.Index(fields=("section", "order")),
        ]

    def __str__(self):
        return f"{self.section}: {self.name}"


class Area(TimeStampedUUIDModel):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="areas",
    )
    category = models.ForeignKey(
        AreaCategory,
        on_delete=models.CASCADE,
        related_name="areas",
    )
    name = models.CharField(max_length=120)
    price = models.PositiveIntegerField()
    promotional_price = models.PositiveIntegerField(blank=True, null=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="waxing/areas/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ("order", "name")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "section",
                name="uq_waxing_area_name_ci_per_section",
            ),
            models.CheckConstraint(
                condition=Q(promotional_price__isnull=True)
                | Q(promotional_price__lt=F("price")),
                name="ck_waxing_area_promo_lt_price",
            ),
        ]
        indexes = [
            models.Index(fields=("section", "category", "order")),
            models.Index(fields=("section", "is_featured")),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if (
            self.section_id
            and self.category_id
            and self.category.section_id != self.section_id
        ):
            errors["category"] = "La categoria debe pertenecer a la misma seccion del area."

        if (
            self.promotional_price is not None
            and self.price is not None
            and self.promotional_price >= self.price
        ):
            errors["promotional_price"] = (
                "promotional_price debe ser menor que price."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        previous_category_id = None
        if self.pk:
            previous_category_id = (
                Area.objects.filter(pk=self.pk)
                .values_list("category_id", flat=True)
                .first()
            )

        if self._state.adding and self.order == 0 and self.category_id:
            self.order = 0
        elif (
            previous_category_id is not None
            and self.category_id is not None
            and previous_category_id != self.category_id
        ):
            self.order = 0
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.section}: {self.name}"

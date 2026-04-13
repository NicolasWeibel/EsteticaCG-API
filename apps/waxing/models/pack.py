from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from .area import Area
from .base import TimeStampedUUIDModel
from .section import Section


class Pack(TimeStampedUUIDModel):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="packs",
    )
    name = models.CharField(max_length=120)
    price = models.PositiveIntegerField()
    promotional_price = models.PositiveIntegerField(blank=True, null=True)
    duration = models.PositiveIntegerField(blank=True, null=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="waxing/packs/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0, db_index=True)
    areas = models.ManyToManyField(
        Area,
        through="PackArea",
        related_name="packs",
    )

    class Meta:
        ordering = ("order", "name")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "section",
                name="uq_waxing_pack_name_ci_per_section",
            ),
            models.CheckConstraint(
                condition=Q(promotional_price__isnull=True)
                | Q(promotional_price__lt=F("price")),
                name="ck_waxing_pack_promo_lt_price",
            ),
            models.CheckConstraint(
                condition=Q(duration__isnull=True) | Q(duration__gt=0),
                name="ck_waxing_pack_duration_gt_0_or_null",
            ),
        ]
        indexes = [
            models.Index(fields=("section", "order")),
            models.Index(fields=("section", "is_featured")),
        ]

    def category_ids(self):
        if not self.pk:
            return []

        return list(
            {
                category_id
                for category_id in self.pack_areas.values_list(
                    "area__category_id", flat=True
                )
                if category_id is not None
            }
        )

    def clean(self):
        super().clean()
        errors = {}

        if (
            self.promotional_price is not None
            and self.price is not None
            and self.promotional_price >= self.price
        ):
            errors["promotional_price"] = "promotional_price debe ser menor que price."
        if self.duration is not None and self.duration <= 0:
            errors["duration"] = "duration debe ser mayor a 0 o null."

        category_count = len(self.category_ids())
        if category_count > 1 and not self.is_featured:
            errors["is_featured"] = (
                "Los packs con areas de multiples categorias deben ser destacados."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def _category_state(self):
        category_ids = self.category_ids()
        if len(category_ids) == 0:
            return ("none", None)
        if len(category_ids) == 1:
            return ("unique", category_ids[0])
        return ("multi", None)

    def _reassign_order_if_transition_to_unique(self, previous_state):
        if not self.pk:
            return

        current_state = self._category_state()
        current_kind, current_category_id = current_state
        if current_kind != "unique":
            return

        previous_kind, previous_category_id = previous_state
        should_reassign = False

        if previous_kind in {"none", "multi"}:
            should_reassign = True
        elif (
            previous_kind == "unique"
            and previous_category_id is not None
            and previous_category_id != current_category_id
        ):
            should_reassign = True

        if not should_reassign:
            return

        # Nuevo criterio: los nuevos o reasignados quedan arriba en manual.
        next_order = 0
        if next_order != self.order:
            Pack.objects.filter(pk=self.pk).update(order=next_order)
            self.order = next_order

    def __str__(self):
        return f"{self.section}: {self.name}"


class PackArea(TimeStampedUUIDModel):
    pack = models.ForeignKey(
        Pack,
        on_delete=models.CASCADE,
        related_name="pack_areas",
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name="area_packs",
    )
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("pack", "area"),
                name="uq_waxing_pack_area_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("pack", "order")),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if (
            self.pack_id
            and self.area_id
            and self.pack.section_id != self.area.section_id
        ):
            errors["area"] = "El area debe pertenecer a la misma seccion del pack."

        if self.pack_id and self.area_id:
            category_ids = set(
                PackArea.objects.filter(pack_id=self.pack_id)
                .exclude(pk=self.pk)
                .values_list("area__category_id", flat=True)
            )
            category_ids.add(self.area.category_id)
            if len(category_ids) > 1 and not self.pack.is_featured:
                errors["pack"] = (
                    "Los packs con areas de multiples categorias deben ser destacados."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        previous_state = self.pack._category_state()
        self.full_clean()
        result = super().save(*args, **kwargs)
        self.pack._reassign_order_if_transition_to_unique(previous_state)
        return result

    def delete(self, *args, **kwargs):
        previous_state = self.pack._category_state()
        result = super().delete(*args, **kwargs)
        self.pack._reassign_order_if_transition_to_unique(previous_state)
        return result

    def __str__(self):
        return f"{self.pack} -> {self.area}"


class FeaturedItemOrder(TimeStampedUUIDModel):
    class ItemKind(models.TextChoices):
        AREA = "area", "Area"
        PACK = "pack", "Pack"

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="featured_orders",
    )
    item_kind = models.CharField(max_length=10, choices=ItemKind.choices)
    item_id = models.UUIDField()
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("section", "item_kind", "item_id"),
                name="uq_waxing_featured_item_unique_per_section",
            ),
        ]
        indexes = [
            models.Index(fields=("section", "order")),
        ]

    def clean(self):
        super().clean()
        errors = {}
        model = Area if self.item_kind == self.ItemKind.AREA else Pack
        item = model.objects.filter(id=self.item_id).first()

        if item is None:
            errors["item_id"] = "El item seleccionado no existe."
        else:
            if item.section_id != self.section_id:
                errors["section"] = (
                    "El item destacado debe pertenecer a la misma seccion."
                )
            if not item.is_featured:
                errors["item_id"] = (
                    "El item debe tener is_featured=True para orden manual."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.section} {self.item_kind} {self.item_id}"

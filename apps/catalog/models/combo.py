from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .item_base import ItemBase
from .filters import Technique, Objective, Intensity
from .base import TimeStampedUUIDModel
from ..services.uniqueness import uniqueness_message


class Combo(ItemBase):
    SESSION_FREQ_WEEK = "week"
    SESSION_FREQ_MONTH = "month"
    SESSION_FREQ_CHOICES = (
        (SESSION_FREQ_WEEK, "Week"),
        (SESSION_FREQ_MONTH, "Month"),
    )

    techniques = models.ManyToManyField(Technique, blank=True)
    objectives = models.ManyToManyField(Objective, blank=True)
    intensities = models.ManyToManyField(Intensity, blank=True)
    # precios del combo en sí:
    price = models.DecimalField(max_digits=10, decimal_places=2)
    promotional_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    sessions = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(0)]
    )
    min_session_interval_days = models.PositiveSmallIntegerField(default=0)
    session_freq = models.CharField(
        max_length=10,
        choices=SESSION_FREQ_CHOICES,
        default=SESSION_FREQ_WEEK,
    )
    session_interval = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    occurrences_per_period = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    duration = models.PositiveIntegerField(null=True, blank=True)

    # reglas declarativas opcionales (zonas seleccionables, máximos, etc.)
    rules = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [*ItemBase.Meta.indexes]
        constraints = [
            models.UniqueConstraint(
                Lower("slug"),
                "category",
                name="uq_combo_slug_category_ci",
                violation_error_message=uniqueness_message("Combo", "slug"),
            ),
            models.UniqueConstraint(
                Lower("title"),
                "category",
                name="uq_combo_title_category_ci",
                violation_error_message=uniqueness_message("Combo", "title"),
            ),
            models.CheckConstraint(
                condition=models.Q(price__gt=0), name="ck_combo_price_gt_0"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(promotional_price__isnull=True)
                    | models.Q(promotional_price__gt=0)
                ),
                name="ck_combo_promo_gt_0_or_null",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(promotional_price__isnull=True)
                    | models.Q(promotional_price__lt=models.F("price"))
                ),
                name="ck_combo_promo_lt_price",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_active=True, sessions__gte=1)
                    | models.Q(is_active=False, sessions__gte=0)
                ),
                name="ck_combo_sessions_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(min_session_interval_days__gte=0),
                name="ck_combo_min_session_interval_days_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(session_interval__gte=1),
                name="ck_combo_session_interval_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(occurrences_per_period__gte=1),
                name="ck_combo_occurrences_per_period_gte_1",
            ),
            models.CheckConstraint(
                condition=(models.Q(duration__isnull=True) | models.Q(duration__gt=0)),
                name="ck_combo_duration_gt_0_or_null",
            ),
        ]


@receiver(m2m_changed, sender=Combo.objectives.through)
def validate_combo_objectives(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    if action not in ("pre_add", "pre_set") or reverse:
        return
    if not pk_set:
        return
    qs = Objective.objects.filter(pk__in=pk_set)
    if qs.filter(category__isnull=True).exists():
        raise ValidationError("Los objetivos deben tener una categor\u00eda.")
    if qs.exclude(category_id=instance.category_id).exists():
        raise ValidationError("Los objetivos deben ser de la misma categor\u00eda.")


class ComboIngredient(TimeStampedUUIDModel):
    combo = models.ForeignKey(
        Combo, on_delete=models.CASCADE, related_name="ingredients"
    )
    treatment_zone_config = models.ForeignKey(
        "TreatmentZoneConfig",
        on_delete=models.CASCADE,
        related_name="combo_ingredients",
    )

    class Meta:
        unique_together = ("combo", "treatment_zone_config")
        indexes = [models.Index(fields=["combo", "treatment_zone_config"])]

    def clean(self):
        super().clean()
        tzc = self.treatment_zone_config

        # Categoría coherente con el combo
        if tzc.treatment.category_id != self.combo.category_id:
            raise ValidationError(
                "El tratamiento del ingrediente debe ser de la misma categoria que el combo."
            )
        if tzc.zone.category_id != self.combo.category_id:
            raise ValidationError(
                "La zona del ingrediente debe ser de la misma categoria que el combo."
            )

        # Jornada coherente con el combo (o addon permitido)
        combo_journey = self.combo.journey
        treatment_journey = tzc.treatment.journey
        if combo_journey and treatment_journey and treatment_journey != combo_journey:
            is_addon = combo_journey.addons.filter(id=tzc.treatment_id).exists()
            if not is_addon:
                raise ValidationError(
                    f"El tratamiento '{tzc.treatment.title}' pertenece a otra Jornada ('{treatment_journey}') "
                    f"y no esta habilitado como 'addon' en la Jornada del Combo ('{combo_journey}')."
                )

    def __str__(self) -> str:
        tzc = self.treatment_zone_config
        try:
            treatment = tzc.treatment.title
            zone = tzc.zone.name
            price = tzc.price
            promo = tzc.promotional_price
            price_str = f"{promo} ({price})" if promo else f"{price}"
            return f"{treatment} / {zone} / {price_str}"
        except Exception:
            return f"ComboIngredient {self.pk}"


class ComboSessionItem(TimeStampedUUIDModel):
    combo = models.ForeignKey(
        Combo, on_delete=models.CASCADE, related_name="session_items"
    )
    session_index = models.PositiveSmallIntegerField()
    ingredient = models.ForeignKey(ComboIngredient, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(session_index__gte=1),
                name="ck_combo_session_index_gte_1",
            ),
            models.UniqueConstraint(
                fields=["combo", "session_index", "ingredient"],
                name="uq_combo_session_item_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["combo", "session_index"]),
            models.Index(fields=["ingredient"]),
        ]

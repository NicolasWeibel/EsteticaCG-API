from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from .item_base import ItemBase
from .base import TimeStampedUUIDModel


class Combo(ItemBase):
    # precios del combo en sí:
    price = models.DecimalField(max_digits=10, decimal_places=2)
    promotional_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    sessions = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    min_session_interval_days = models.PositiveSmallIntegerField(default=0)

    # reglas declarativas opcionales (zonas seleccionables, máximos, etc.)
    rules = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gt=0), name="ck_combo_price_gt_0"
            ),
            models.CheckConstraint(
                check=(
                    models.Q(promotional_price__isnull=True)
                    | models.Q(promotional_price__gt=0)
                ),
                name="ck_combo_promo_gt_0_or_null",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(promotional_price__isnull=True)
                    | models.Q(promotional_price__lt=models.F("price"))
                ),
                name="ck_combo_promo_lt_price",
            ),
            models.CheckConstraint(
                check=models.Q(sessions__gte=1), name="ck_combo_sessions_gte_1"
            ),
            models.CheckConstraint(
                check=models.Q(min_session_interval_days__gte=0),
                name="ck_combo_min_session_interval_days_gte_0",
            ),
        ]


class ComboIngredient(TimeStampedUUIDModel):
    combo = models.ForeignKey(
        Combo, on_delete=models.CASCADE, related_name="ingredients"
    )
    treatment_zone_config = models.ForeignKey(
        "TreatmentZoneConfig",
        on_delete=models.PROTECT,
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


class ComboStep(TimeStampedUUIDModel):
    class OrderHint(models.TextChoices):
        START = "AL_PRINCIPIO", "Al principio"
        ANY = "AL_MEDIO", "Indistinto"
        END = "AL_FINAL", "Al final"

    combo = models.ForeignKey(Combo, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveIntegerField()  # orden de los grupos de trabajo

    # semántica: algunos pares tratamiento-zona deben ir al principio/medio/final
    # (los ítems adjuntos llevan el hint específico)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["combo", "order"], name="uq_combo_step_order"
            )
        ]
        ordering = ["order"]


class ComboStepItem(TimeStampedUUIDModel):
    step = models.ForeignKey(ComboStep, on_delete=models.CASCADE, related_name="items")
    treatment = models.ForeignKey("Treatment", on_delete=models.PROTECT)
    zone = models.ForeignKey("Zone", on_delete=models.PROTECT, null=True, blank=True)
    duration = models.PositiveIntegerField()
    order_hint = models.CharField(
        max_length=20,
        choices=ComboStep.OrderHint.choices,
        default=ComboStep.OrderHint.ANY,
    )

    class Meta:
        indexes = [models.Index(fields=["step"])]

    def clean(self):
        # coherencia con combo de la step
        combo = self.step.combo

        # 1. Validar Categoría (Existente)
        if self.treatment.category_id != combo.category_id:
            raise ValidationError(
                "El tratamiento del paso debe ser de la misma categoría que el combo."
            )
        if self.zone and self.zone.category_id != combo.category_id:
            raise ValidationError(
                "La zona del paso debe ser de la misma categoría que el combo."
            )
        if self.duration <= 0:
            raise ValidationError("La duración debe ser > 0.")

        # 2. Validar Jornada (Nueva lógica)
        combo_journey = combo.journey
        treatment_journey = self.treatment.journey

        # Solo validamos si ambos tienen jornada definida y son diferentes
        if combo_journey and treatment_journey and treatment_journey != combo_journey:
            # Verificamos si la jornada del combo permite este tratamiento como addon
            is_addon = combo_journey.addons.filter(id=self.treatment.id).exists()

            if not is_addon:
                raise ValidationError(
                    f"El tratamiento '{self.treatment.title}' pertenece a otra Jornada ('{treatment_journey}') "
                    f"y no está habilitado como 'addon' en la Jornada del Combo ('{combo_journey}')."
                )

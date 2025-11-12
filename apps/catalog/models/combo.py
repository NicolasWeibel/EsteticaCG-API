from django.core.exceptions import ValidationError
from django.db import models
from .item_base import ItemBase
from .base import TimeStampedUUIDModel


class Combo(ItemBase):
    # precios del combo en sí:
    price = models.DecimalField(max_digits=10, decimal_places=2)
    promotional_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

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
        ]


class ComboIngredient(TimeStampedUUIDModel):
    combo = models.ForeignKey(
        Combo, on_delete=models.CASCADE, related_name="ingredients"
    )
    treatment = models.ForeignKey("Treatment", on_delete=models.PROTECT)
    zone = models.ForeignKey("Zone", on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        unique_together = ("combo", "treatment", "zone")
        indexes = [models.Index(fields=["combo", "treatment"])]

    def clean(self):
        if self.treatment.category_id != self.combo.category_id:  # type: ignore[attr-defined]
            raise ValidationError(
                "El tratamiento del ingrediente debe ser de la misma categoría que el combo."
            )
        if self.zone and self.zone.category_id != self.combo.category_id:  # type: ignore[attr-defined]
            raise ValidationError(
                "La zona del ingrediente debe ser de la misma categoría que el combo."
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
        if self.treatment.category_id != combo.category_id:  # type: ignore[attr-defined]
            raise ValidationError(
                "El tratamiento del paso debe ser de la misma categoría que el combo."
            )
        if self.zone and self.zone.category_id != combo.category_id:  # type: ignore[attr-defined]
            raise ValidationError(
                "La zona del paso debe ser de la misma categoría que el combo."
            )
        if self.duration <= 0:
            raise ValidationError("La duración debe ser > 0.")

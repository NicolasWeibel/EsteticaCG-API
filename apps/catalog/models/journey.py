# apps/catalog/models/journey.py

from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from .base import TimeStampedUUIDModel
from .category import Category
from .treatment import Treatment


class Journey(TimeStampedUUIDModel):
    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="journeys"
    )
    addons = models.ManyToManyField(
        "catalog.Treatment",
        related_name="addon_in_journeys",
        blank=True,  # ✅ string ref
    )

    def clean(self):
        super().clean()
        cat_id = self.category_id
        if not cat_id:
            return
        bad_cat = [a for a in self.addons.all() if a.category_id != cat_id]
        if bad_cat:
            raise ValidationError("Los addons deben ser de la misma categoría.")
        same_journey = [a for a in self.addons.all() if a.journey_id == self.id]
        if same_journey:
            raise ValidationError("Los addons no pueden pertenecer a la misma jornada.")

    def __str__(self):
        return self.title


@receiver(m2m_changed, sender=Journey.addons.through)
def validate_addons(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action not in ("pre_add", "pre_set") or reverse:
        return
    cat_id = instance.category_id
    if not cat_id or not pk_set:
        return
    qs = Treatment.objects.filter(pk__in=pk_set)
    if qs.exclude(category_id=cat_id).exists():
        raise ValidationError("Los addons deben ser de la misma categoría.")
    if instance.pk and qs.filter(journey_id=instance.pk).exists():
        raise ValidationError("Los addons no pueden pertenecer a la misma jornada.")

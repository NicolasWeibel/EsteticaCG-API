from django.db.models.signals import post_save
from django.dispatch import receiver
from .models.treatment import TreatmentZoneConfig
from .models.incompatibility import TreatmentZoneIncompatibility, positions_overlap


@receiver(post_save, sender=TreatmentZoneConfig)
def purge_invalid_incompatibilities(sender, instance: TreatmentZoneConfig, **kwargs):
    """
    Revalida incompatibilidades al guardar un TZC:
      - elimina las que ya no solapan por body_position
      - elimina las que quedaron en misma zona
      - elimina las que divergen de categoría (excepcional)
    """
    # pares donde instance es left
    left_qs = TreatmentZoneIncompatibility.objects.filter(
        left_tzc=instance
    ).select_related("right_tzc", "right_tzc__treatment", "right_tzc__zone")
    for inc in left_qs:
        a = instance
        b = inc.right_tzc
        if (
            a.zone_id == b.zone_id
            or a.treatment.category_id != b.treatment.category_id  # type: ignore[attr-defined]
            or not positions_overlap(a.body_position, b.body_position)
        ):
            inc.delete()

    # pares donde instance es right
    right_qs = TreatmentZoneIncompatibility.objects.filter(
        right_tzc=instance
    ).select_related("left_tzc", "left_tzc__treatment", "left_tzc__zone")
    for inc in right_qs:
        a = instance
        b = inc.left_tzc
        if (
            a.zone_id == b.zone_id
            or a.treatment.category_id != b.treatment.category_id  # type: ignore[attr-defined]
            or not positions_overlap(a.body_position, b.body_position)
        ):
            inc.delete()

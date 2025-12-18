from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import cloudinary.uploader

from .models.treatment import TreatmentZoneConfig
from .models.incompatibility import TreatmentZoneIncompatibility, positions_overlap
from .models import TreatmentImage, ComboImage, JourneyImage


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


# =========================
# Galería: cleanup + orden
# =========================

def delete_cloudinary_file(image_field):
    if image_field:
        try:
            cloudinary.uploader.destroy(image_field.name)
        except Exception as exc:
            print(f"Error Cloudinary: {exc}")


def reorder_siblings(queryset):
    with transaction.atomic():
        updates = []
        for index, img in enumerate(queryset.order_by("order")):
            if img.order != index:
                img.order = index
                updates.append(img)
        if updates:
            queryset.model.objects.bulk_update(updates, ["order"])


@receiver(post_delete, sender=TreatmentImage)
def cleanup_treatment_image(sender, instance, **kwargs):
    delete_cloudinary_file(instance.image)
    reorder_siblings(instance.treatment.images.all())


@receiver(post_delete, sender=ComboImage)
def cleanup_combo_image(sender, instance, **kwargs):
    delete_cloudinary_file(instance.image)
    reorder_siblings(instance.combo.images.all())


@receiver(post_delete, sender=JourneyImage)
def cleanup_journey_image(sender, instance, **kwargs):
    delete_cloudinary_file(instance.image)
    reorder_siblings(instance.journey.images.all())

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

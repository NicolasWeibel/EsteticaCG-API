import threading
from django.db import transaction
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.dispatch import receiver
import cloudinary.uploader

from .models.treatment import TreatmentZoneConfig, Treatment
from .models.incompatibility import TreatmentZoneIncompatibility, positions_overlap
from .models import (
    TreatmentMedia,
    ComboMedia,
    JourneyMedia,
    Journey,
    Combo,
    ComboIngredient,
    ComboSessionItem,
    Category,
    Objective,
)
from .models.placement import PlacementItem
from .services.commands import (
    cleanup_combo_deactivation,
    deactivate_empty_combo,
    deactivate_combos as service_deactivate_combos,
    deactivate_treatments as service_deactivate_treatments,
    remove_items_from_placements,
)


_tzc_delete_state = threading.local()
_addons_state = threading.local()


def _get_tzc_combo_map():
    combo_map = getattr(_tzc_delete_state, "combo_map", None)
    if combo_map is None:
        combo_map = {}
        _tzc_delete_state.combo_map = combo_map
    return combo_map


def _get_addon_map():
    treatment_map = getattr(_addons_state, "treatment_map", None)
    if treatment_map is None:
        treatment_map = {}
        _addons_state.treatment_map = treatment_map
    return treatment_map


def _get_affected_combo_ids_by_treatments(treatment_ids, journey_id=None):
    ids = [treatment_id for treatment_id in (treatment_ids or []) if treatment_id]
    if not ids:
        return set()
    qs = ComboIngredient.objects.filter(treatment_zone_config__treatment_id__in=ids)
    if journey_id is not None:
        qs = qs.filter(combo__journey_id=journey_id)
    return set(qs.values_list("combo_id", flat=True))


def _delete_ingredients_by_treatments(treatment_ids, journey_id=None):
    ids = [treatment_id for treatment_id in (treatment_ids or []) if treatment_id]
    if not ids:
        return
    qs = ComboIngredient.objects.filter(treatment_zone_config__treatment_id__in=ids)
    if journey_id is not None:
        qs = qs.filter(combo__journey_id=journey_id)
    qs.delete()


def _deactivate_combos(combo_ids):
    """
    Deactivate combos by delegating to the service layer.

    This wrapper exists to keep signal orchestration thin while the explicit
    deactivation behavior lives in the service layer.
    """
    service_deactivate_combos(combo_ids)


def _deactivate_treatments(treatment_ids):
    """
    Deactivate treatments by delegating to the service layer.

    This wrapper exists to keep signal orchestration thin while the explicit
    deactivation behavior lives in the service layer.
    """
    service_deactivate_treatments(treatment_ids)


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


def delete_cloudinary_file(media_field, media_type=None):
    if media_field:
        try:
            kwargs = {}
            if media_type == "video":
                kwargs["resource_type"] = "video"
            cloudinary.uploader.destroy(media_field.name, **kwargs)
        except Exception as exc:
            print(f"Error Cloudinary: {exc}")


def capture_old_image_for_cleanup(instance, field_name):
    """
    Capture old image reference before saving (pre_save).
    Stores it temporarily so we can delete it AFTER the new one is saved successfully.
    This prevents data loss if the new image upload fails.
    """
    if not instance.pk:
        return  # New instance, no old image to delete

    try:
        old_instance = instance.__class__.objects.get(pk=instance.pk)
        old_image = getattr(old_instance, field_name, None)
        new_image = getattr(instance, field_name, None)

        # If the image changed, store the old one for cleanup after save
        if old_image and old_image != new_image:
            if not hasattr(instance, "_old_images_to_cleanup"):
                instance._old_images_to_cleanup = []
            instance._old_images_to_cleanup.append(old_image)
    except instance.__class__.DoesNotExist:
        pass  # Instance doesn't exist yet, nothing to cleanup


def cleanup_old_images_after_save(instance):
    """
    Delete old images from Cloudinary after new images were saved successfully (post_save).
    Only deletes images that were captured in pre_save.
    """
    if hasattr(instance, "_old_images_to_cleanup"):
        for old_image in instance._old_images_to_cleanup:
            delete_cloudinary_file(old_image)
        delattr(instance, "_old_images_to_cleanup")


def reorder_siblings(queryset):
    with transaction.atomic():
        updates = []
        for index, img in enumerate(queryset.order_by("order")):
            if img.order != index:
                img.order = index
                updates.append(img)
        if updates:
            queryset.model.objects.bulk_update(updates, ["order"])


@receiver(post_delete, sender=TreatmentMedia)
def cleanup_treatment_media(sender, instance, **kwargs):
    delete_cloudinary_file(instance.media, instance.media_type)
    reorder_siblings(instance.treatment.media.all())


@receiver(post_delete, sender=ComboMedia)
def cleanup_combo_media(sender, instance, **kwargs):
    delete_cloudinary_file(instance.media, instance.media_type)
    reorder_siblings(instance.combo.media.all())


@receiver(post_delete, sender=JourneyMedia)
def cleanup_journey_media(sender, instance, **kwargs):
    delete_cloudinary_file(instance.media, instance.media_type)
    reorder_siblings(instance.journey.media.all())


# =========================
# Combo: compactar sesiones
# =========================


def _compact_combo_sessions(combo_id):
    combo = Combo.objects.filter(id=combo_id).first()
    if not combo:
        return

    ingredients_exist = ComboIngredient.objects.filter(combo_id=combo_id).exists()
    if not ingredients_exist:
        deactivate_empty_combo(combo_id)
        return

    items = list(
        ComboSessionItem.objects.filter(combo_id=combo_id).order_by(
            "session_index", "id"
        )
    )
    if not items:
        if combo.is_active and combo.sessions <= 0:
            Combo.objects.filter(id=combo_id).update(sessions=1)
        return

    seen = set()
    ordered_indices = []
    for item in items:
        idx = item.session_index
        if idx not in seen:
            seen.add(idx)
            ordered_indices.append(idx)

    mapping = {old: new for new, old in enumerate(ordered_indices, start=1)}
    to_update = []
    for item in items:
        new_idx = mapping[item.session_index]
        if new_idx != item.session_index:
            item.session_index = new_idx
            to_update.append(item)
    if to_update:
        ComboSessionItem.objects.bulk_update(to_update, ["session_index"])

    new_total = len(ordered_indices)
    if combo.sessions != new_total:
        Combo.objects.filter(id=combo_id).update(sessions=new_total)


@receiver(post_delete, sender=ComboIngredient)
def compact_sessions_on_ingredient_delete(sender, instance, **kwargs):
    combo_id = instance.combo_id
    if not combo_id:
        return
    if not Combo.objects.filter(id=combo_id).exists():
        return
    _compact_combo_sessions(combo_id)


@receiver(pre_delete, sender=TreatmentZoneConfig)
def capture_combo_ids_for_tzc_delete(sender, instance, **kwargs):
    combo_ids = list(
        ComboIngredient.objects.filter(
            treatment_zone_config_id=instance.id
        ).values_list("combo_id", flat=True)
    )
    if combo_ids:
        combo_map = _get_tzc_combo_map()
        combo_map[instance.id] = set(combo_ids)


@receiver(post_delete, sender=TreatmentZoneConfig)
def deactivate_combos_and_treatment_on_tzc_delete(sender, instance, **kwargs):
    combo_map = _get_tzc_combo_map()
    combo_ids = combo_map.pop(instance.id, None)
    _deactivate_combos(combo_ids)

    treatment_id = instance.treatment_id
    if (
        treatment_id
        and not TreatmentZoneConfig.objects.filter(treatment_id=treatment_id).exists()
    ):
        _deactivate_treatments([treatment_id])


@receiver(m2m_changed, sender=Journey.addons.through)
def handle_journey_addons_remove(sender, instance, action, reverse, pk_set, **kwargs):
    if reverse:
        return
    addon_map = _get_addon_map()
    if action == "pre_clear":
        addon_map[instance.id] = set(instance.addons.values_list("id", flat=True))
        return

    removed_treatment_ids = set()
    if action == "post_remove":
        removed_treatment_ids = set(pk_set or [])
    elif action == "post_clear":
        removed_treatment_ids = addon_map.pop(instance.id, set())

    if not removed_treatment_ids:
        return

    combo_ids = _get_affected_combo_ids_by_treatments(
        removed_treatment_ids,
        journey_id=instance.id,
    )
    _delete_ingredients_by_treatments(
        removed_treatment_ids,
        journey_id=instance.id,
    )
    _deactivate_combos(combo_ids)


@receiver(post_delete, sender=Treatment)
def cleanup_treatment_from_placements_on_delete(sender, instance, **kwargs):
    """Remove deleted treatment from any placements and cleanup images."""
    delete_cloudinary_file(instance.benefits_image)
    delete_cloudinary_file(instance.recommended_image)
    remove_items_from_placements(
        PlacementItem.ItemKind.TREATMENT,
        [instance.id],
    )


# =========================
# Combo: placement cleanup
# =========================


@receiver(post_delete, sender=Combo)
def cleanup_combo_from_placements_on_delete(sender, instance, **kwargs):
    """Remove deleted combo from any placements and cleanup images."""
    delete_cloudinary_file(instance.benefits_image)
    delete_cloudinary_file(instance.recommended_image)
    cleanup_combo_deactivation([instance.id])


@receiver(post_delete, sender=Journey)
def cleanup_journey_images_on_delete(sender, instance, **kwargs):
    """Cleanup journey images from Cloudinary."""
    delete_cloudinary_file(instance.benefits_image)
    delete_cloudinary_file(instance.recommended_image)


@receiver(post_delete, sender=Category)
def cleanup_category_image_on_delete(sender, instance, **kwargs):
    """Cleanup category image from Cloudinary."""
    delete_cloudinary_file(instance.image)


@receiver(post_delete, sender=Objective)
def cleanup_objective_image_on_delete(sender, instance, **kwargs):
    """Cleanup objective image from Cloudinary."""
    delete_cloudinary_file(instance.image)


# =========================
# Image replacement cleanup
# =========================


@receiver(pre_save, sender=Treatment)
def capture_treatment_old_images(sender, instance, **kwargs):
    """Capture old images before saving."""
    capture_old_image_for_cleanup(instance, "benefits_image")
    capture_old_image_for_cleanup(instance, "recommended_image")


@receiver(post_save, sender=Treatment)
def cleanup_treatment_old_images(sender, instance, **kwargs):
    """Cleanup old images after new ones are saved successfully."""
    cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=Combo)
def capture_combo_old_images(sender, instance, **kwargs):
    """Capture old images before saving."""
    capture_old_image_for_cleanup(instance, "benefits_image")
    capture_old_image_for_cleanup(instance, "recommended_image")


@receiver(post_save, sender=Combo)
def cleanup_combo_old_images(sender, instance, **kwargs):
    """Cleanup old images after new ones are saved successfully."""
    cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=Journey)
def capture_journey_old_images(sender, instance, **kwargs):
    """Capture old images before saving."""
    capture_old_image_for_cleanup(instance, "benefits_image")
    capture_old_image_for_cleanup(instance, "recommended_image")


@receiver(post_save, sender=Journey)
def cleanup_journey_old_images(sender, instance, **kwargs):
    """Cleanup old images after new ones are saved successfully."""
    cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=Category)
def capture_category_old_image(sender, instance, **kwargs):
    """Capture old image before saving."""
    capture_old_image_for_cleanup(instance, "image")


@receiver(post_save, sender=Category)
def cleanup_category_old_image(sender, instance, **kwargs):
    """Cleanup old image after new one is saved successfully."""
    cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=Objective)
def capture_objective_old_image(sender, instance, **kwargs):
    """Capture old image before saving."""
    capture_old_image_for_cleanup(instance, "image")


@receiver(post_save, sender=Objective)
def cleanup_objective_old_image(sender, instance, **kwargs):
    """Cleanup old image after new one is saved successfully."""
    cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=TreatmentMedia)
def capture_treatment_media_old(sender, instance, **kwargs):
    """Capture old media before saving."""
    capture_old_image_for_cleanup(instance, "media")


@receiver(post_save, sender=TreatmentMedia)
def cleanup_treatment_media_old(sender, instance, **kwargs):
    """Cleanup old media after new one is saved successfully."""
    cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=ComboMedia)
def capture_combo_media_old(sender, instance, **kwargs):
    """Capture old media before saving."""
    capture_old_image_for_cleanup(instance, "media")


@receiver(post_save, sender=ComboMedia)
def cleanup_combo_media_old(sender, instance, **kwargs):
    """Cleanup old media after new one is saved successfully."""
    cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=JourneyMedia)
def capture_journey_media_old(sender, instance, **kwargs):
    """Capture old media before saving."""
    capture_old_image_for_cleanup(instance, "media")


@receiver(post_save, sender=JourneyMedia)
def cleanup_journey_media_old(sender, instance, **kwargs):
    """Cleanup old media after new one is saved successfully."""
    cleanup_old_images_after_save(instance)

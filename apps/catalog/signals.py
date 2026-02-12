import threading
from django.db import transaction
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
import cloudinary.uploader

from .models.treatment import TreatmentZoneConfig, Treatment
from .models.incompatibility import TreatmentZoneIncompatibility, positions_overlap
from .models import (
    TreatmentMedia,
    ComboMedia,
    JourneyMedia,
    Combo,
    ComboIngredient,
    ComboSessionItem,
)


_tzc_delete_state = threading.local()


def _get_tzc_combo_map():
    combo_map = getattr(_tzc_delete_state, "combo_map", None)
    if combo_map is None:
        combo_map = {}
        _tzc_delete_state.combo_map = combo_map
    return combo_map


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

    ingredients_exist = ComboIngredient.objects.filter(
        combo_id=combo_id
    ).exists()
    if not ingredients_exist:
        updates = {}
        if combo.is_active:
            updates["is_active"] = False
        if combo.sessions != 0:
            updates["sessions"] = 0
        if updates:
            Combo.objects.filter(id=combo_id).update(**updates)
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
    if combo_ids:
        Combo.objects.filter(id__in=combo_ids).update(is_active=False)

    treatment_id = instance.treatment_id
    if treatment_id and not TreatmentZoneConfig.objects.filter(
        treatment_id=treatment_id
    ).exists():
        Treatment.objects.filter(id=treatment_id).update(is_active=False)

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
)


_tzc_delete_state = threading.local()
_addons_state = threading.local()
_treatment_state = threading.local()


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


def _get_treatment_active_map():
    state_map = getattr(_treatment_state, "active_map", None)
    if state_map is None:
        state_map = {}
        _treatment_state.active_map = state_map
    return state_map


def _get_affected_combo_ids_by_treatments(treatment_ids, journey_id=None):
    ids = [treatment_id for treatment_id in (treatment_ids or []) if treatment_id]
    if not ids:
        return set()
    qs = ComboIngredient.objects.filter(
        treatment_zone_config__treatment_id__in=ids
    )
    if journey_id is not None:
        qs = qs.filter(combo__journey_id=journey_id)
    return set(qs.values_list("combo_id", flat=True))


def _delete_ingredients_by_treatments(treatment_ids, journey_id=None):
    ids = [treatment_id for treatment_id in (treatment_ids or []) if treatment_id]
    if not ids:
        return
    qs = ComboIngredient.objects.filter(
        treatment_zone_config__treatment_id__in=ids
    )
    if journey_id is not None:
        qs = qs.filter(combo__journey_id=journey_id)
    qs.delete()


def _deactivate_combos(combo_ids):
    ids = [combo_id for combo_id in (combo_ids or []) if combo_id]
    if not ids:
        return
    Combo.objects.filter(id__in=ids).update(is_active=False)


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
    _deactivate_combos(combo_ids)

    treatment_id = instance.treatment_id
    if treatment_id and not TreatmentZoneConfig.objects.filter(
        treatment_id=treatment_id
    ).exists():
        Treatment.objects.filter(id=treatment_id).update(is_active=False)


@receiver(m2m_changed, sender=Journey.addons.through)
def handle_journey_addons_remove(
    sender, instance, action, reverse, pk_set, **kwargs
):
    if reverse:
        return
    addon_map = _get_addon_map()
    if action == "pre_clear":
        addon_map[instance.id] = set(
            instance.addons.values_list("id", flat=True)
        )
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


@receiver(pre_save, sender=Treatment)
def capture_previous_treatment_active_state(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous_state = Treatment.objects.filter(id=instance.id).values_list(
        "is_active", flat=True
    ).first()
    state_map = _get_treatment_active_map()
    state_map[instance.id] = previous_state


@receiver(post_save, sender=Treatment)
def deactivate_combos_on_treatment_deactivation(sender, instance, created, **kwargs):
    if created:
        return
    state_map = _get_treatment_active_map()
    previous_active = state_map.pop(instance.id, None)
    if previous_active is not True or instance.is_active:
        return

    combo_ids = _get_affected_combo_ids_by_treatments([instance.id])
    _deactivate_combos(combo_ids)

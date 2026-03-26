"""
Catalog service commands for explicit business logic orchestration.

This module contains functions that orchestrate cascading business operations
across multiple models. Signal handlers should remain thin and delegate to
these functions when cross-model coordination is needed.
"""

from django.db import transaction
from typing import Collection
from uuid import UUID


def _normalize_ids(item_ids: Collection[UUID] | None) -> list[UUID]:
    return [item_id for item_id in (item_ids or []) if item_id]


def _affected_combo_ids_by_treatments(treatment_ids: Collection[UUID] | None) -> list[UUID]:
    ids = _normalize_ids(treatment_ids)
    if not ids:
        return []

    from ..models.combo import ComboIngredient

    return list(
        ComboIngredient.objects.filter(treatment_zone_config__treatment_id__in=ids)
        .values_list("combo_id", flat=True)
        .distinct()
    )


def remove_items_from_placements(
    item_kind: str,
    item_ids: Collection[UUID] | None,
) -> int:
    """
    Remove PlacementItems that reference the given item_kind and item_ids.

    This function is idempotent and safe to call with empty item_ids.

    Args:
        item_kind: The type of item ("treatment", "combo", "journey").
        item_ids: Collection of UUIDs to remove from placements.

    Returns:
        Number of PlacementItems deleted.
    """
    from ..models.placement import PlacementItem

    ids = _normalize_ids(item_ids)
    if not ids:
        return 0

    deleted_count, _ = PlacementItem.objects.filter(
        item_kind=item_kind,
        item_id__in=ids,
    ).delete()
    return deleted_count


def cleanup_combo_deactivation(combo_ids: Collection[UUID] | None) -> int:
    from ..models.placement import PlacementItem

    ids = _normalize_ids(combo_ids)
    if not ids:
        return 0

    return remove_items_from_placements(PlacementItem.ItemKind.COMBO, ids)


def cleanup_treatment_deactivation(treatment_ids: Collection[UUID] | None) -> int:
    from ..models.placement import PlacementItem

    ids = _normalize_ids(treatment_ids)
    if not ids:
        return 0

    deleted = remove_items_from_placements(PlacementItem.ItemKind.TREATMENT, ids)
    deactivate_combos(_affected_combo_ids_by_treatments(ids))
    return deleted


def deactivate_combos(combo_ids: Collection[UUID] | None) -> int:
    """
    Deactivate combos by ID and apply deactivation side effects explicitly.

    This function is idempotent and safe to call with empty combo_ids.

    Args:
        combo_ids: Collection of combo UUIDs to deactivate.

    Returns:
        Number of combos actually deactivated (transitioned from active to inactive).
    """
    from ..models.combo import Combo

    ids = _normalize_ids(combo_ids)
    if not ids:
        return 0

    active_ids = list(
        Combo.objects.filter(id__in=ids, is_active=True).values_list("id", flat=True)
    )
    if not active_ids:
        return 0

    with transaction.atomic():
        Combo.objects.filter(id__in=active_ids).update(is_active=False)
        cleanup_combo_deactivation(active_ids)

    return len(active_ids)


def deactivate_treatments(treatment_ids: Collection[UUID] | None) -> int:
    """
    Deactivate treatments by ID and apply deactivation side effects explicitly.

    This function is idempotent and safe to call with empty treatment_ids.

    Args:
        treatment_ids: Collection of treatment UUIDs to deactivate.

    Returns:
        Number of treatments actually deactivated (transitioned from active to inactive).
    """
    from ..models.treatment import Treatment

    ids = _normalize_ids(treatment_ids)
    if not ids:
        return 0

    active_ids = list(
        Treatment.objects.filter(id__in=ids, is_active=True).values_list("id", flat=True)
    )
    if not active_ids:
        return 0

    with transaction.atomic():
        Treatment.objects.filter(id__in=active_ids).update(is_active=False)
        cleanup_treatment_deactivation(active_ids)

    return len(active_ids)


def deactivate_empty_combo(combo_id: UUID | None) -> bool:
    """
    Deactivate a combo that has no ingredients left and normalize sessions to 0.

    This preserves the combo check constraint by applying `is_active=False` and
    `sessions=0` together when the combo is currently active.

    Returns:
        True if the combo transitioned from active to inactive, otherwise False.
    """
    if not combo_id:
        return False

    from ..models.combo import Combo

    combo = Combo.objects.filter(id=combo_id).only("id", "is_active", "sessions").first()
    if not combo:
        return False

    with transaction.atomic():
        if combo.is_active:
            Combo.objects.filter(id=combo_id).update(is_active=False, sessions=0)
            cleanup_combo_deactivation([combo_id])
            return True

        if combo.sessions != 0:
            Combo.objects.filter(id=combo_id).update(sessions=0)

    return False

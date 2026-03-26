"""
Tests for automatic PlacementItem cleanup when Treatments or Combos
are deleted or deactivated.

Responsibilities:
- Treatment: removes itself from placements on delete or deactivation.
- Combo: removes itself from placements on delete or deactivation.
- When Treatment deactivation cascades to Combo deactivation, each entity
  handles its own placement cleanup.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.catalog.models import (
    Category,
    Combo,
    ComboIngredient,
    ComboSessionItem,
    Placement,
    PlacementItem,
    Treatment,
    TreatmentZoneConfig,
    Zone,
)
from apps.catalog.services.commands import (
    deactivate_combos,
    deactivate_treatments,
    remove_items_from_placements,
)


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _make_staff():
    User = get_user_model()
    return User.objects.create_user(
        email=f"{_uid('staff')}@test.com",
        password="test1234",
        is_staff=True,
        is_active=True,
    )


def _make_category() -> Category:
    return Category.objects.create(name=_uid("cat"), slug=_uid("cat-slug"))


def _make_zone(category: Category) -> Zone:
    return Zone.objects.create(name=_uid("zone"), category=category)


def _make_treatment(category: Category, *, is_active: bool = True) -> Treatment:
    return Treatment.objects.create(
        category=category,
        slug=_uid("treatment-slug"),
        title=_uid("Treatment"),
        is_active=is_active,
    )


def _make_combo(
    category: Category, *, is_active: bool = True, sessions: int = 1
) -> Combo:
    return Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=200,
        sessions=sessions,
        is_active=is_active,
    )


def _make_placement() -> Placement:
    return Placement.objects.create(
        slug=_uid("pl-slug"),
        title=_uid("Placement"),
    )


def _add_to_placement(placement: Placement, item, item_kind: str) -> PlacementItem:
    return PlacementItem.objects.create(
        placement=placement,
        item_kind=item_kind,
        item_id=item.id,
        order=0,
    )


# =====================
# Service layer tests
# =====================


@pytest.mark.django_db
def test_remove_items_from_placements_removes_matching_items():
    category = _make_category()
    treatment = _make_treatment(category)
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)

    assert PlacementItem.objects.filter(item_id=treatment.id).exists()

    count = remove_items_from_placements(
        PlacementItem.ItemKind.TREATMENT,
        [treatment.id],
    )

    assert count == 1
    assert not PlacementItem.objects.filter(item_id=treatment.id).exists()


@pytest.mark.django_db
def test_remove_items_from_placements_ignores_empty_ids():
    count = remove_items_from_placements(PlacementItem.ItemKind.TREATMENT, [])
    assert count == 0

    count = remove_items_from_placements(PlacementItem.ItemKind.TREATMENT, None)
    assert count == 0


@pytest.mark.django_db
def test_remove_items_from_placements_only_removes_specified_kind():
    category = _make_category()
    treatment = _make_treatment(category)
    combo = _make_combo(category)
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    # Try to remove as combo (should not affect treatment)
    remove_items_from_placements(PlacementItem.ItemKind.COMBO, [treatment.id])

    assert PlacementItem.objects.filter(
        item_kind=PlacementItem.ItemKind.TREATMENT,
        item_id=treatment.id,
    ).exists()


@pytest.mark.django_db
def test_deactivate_combos_service_triggers_signals():
    category = _make_category()
    combo = _make_combo(category, is_active=True)
    placement = _make_placement()
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    assert PlacementItem.objects.filter(item_id=combo.id).exists()

    count = deactivate_combos([combo.id])

    assert count == 1
    combo.refresh_from_db()
    assert combo.is_active is False
    assert not PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_deactivate_combos_service_ignores_already_inactive():
    category = _make_category()
    combo = _make_combo(category, is_active=False)

    count = deactivate_combos([combo.id])

    assert count == 0


@pytest.mark.django_db
def test_deactivate_combos_service_ignores_empty_ids():
    count = deactivate_combos([])
    assert count == 0

    count = deactivate_combos(None)
    assert count == 0


@pytest.mark.django_db
def test_deactivate_treatments_service_triggers_signals():
    category = _make_category()
    treatment = _make_treatment(category, is_active=True)
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)

    assert PlacementItem.objects.filter(item_id=treatment.id).exists()

    count = deactivate_treatments([treatment.id])

    assert count == 1
    treatment.refresh_from_db()
    assert treatment.is_active is False
    assert not PlacementItem.objects.filter(item_id=treatment.id).exists()


# =========================
# Treatment signal tests
# =========================


@pytest.mark.django_db
def test_delete_treatment_removes_its_placement_item():
    category = _make_category()
    treatment = _make_treatment(category)
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)

    treatment_id = treatment.id
    treatment.delete()

    assert not PlacementItem.objects.filter(item_id=treatment_id).exists()


@pytest.mark.django_db
def test_deactivate_treatment_removes_its_placement_item():
    category = _make_category()
    treatment = _make_treatment(category, is_active=True)
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)

    deactivate_treatments([treatment.id])

    assert not PlacementItem.objects.filter(item_id=treatment.id).exists()


@pytest.mark.django_db
def test_no_placement_change_when_treatment_stays_active():
    category = _make_category()
    treatment = _make_treatment(category, is_active=True)
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)

    treatment.title = "Updated title"
    treatment.save(update_fields=["title"])

    assert PlacementItem.objects.filter(item_id=treatment.id).exists()


@pytest.mark.django_db
def test_no_placement_change_when_treatment_stays_inactive():
    category = _make_category()
    treatment = _make_treatment(category, is_active=False)
    placement = _make_placement()
    # Manually add inactive treatment to placement (edge case)
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)

    treatment.title = "Updated title"
    treatment.save(update_fields=["title"])

    # Should still be there (no transition happened)
    assert PlacementItem.objects.filter(item_id=treatment.id).exists()


@pytest.mark.django_db
def test_deactivate_treatment_cascades_to_combo_and_both_leave_placements():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)

    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    deactivate_treatments([treatment.id])

    combo.refresh_from_db()
    assert combo.is_active is False

    # Both should be removed from placements
    assert not PlacementItem.objects.filter(item_id=treatment.id).exists()
    assert not PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_delete_treatment_cascades_to_combo_deactivation_and_placement_cleanup():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)

    placement = _make_placement()
    treatment_id = treatment.id
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    treatment.delete()

    combo.refresh_from_db()
    assert combo.is_active is False

    # Both should be removed from placements
    assert not PlacementItem.objects.filter(item_id=treatment_id).exists()
    assert not PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_delete_last_tzc_deactivates_treatment_and_removes_it_from_placement():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)

    tzc.delete()

    treatment.refresh_from_db()
    assert treatment.is_active is False
    assert not PlacementItem.objects.filter(item_id=treatment.id).exists()


@pytest.mark.django_db
def test_api_treatment_deactivation_cleans_placements_and_related_combos():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    resp = client.patch(
        f"/api/v1/catalog/treatments/{treatment.id}/",
        {"is_active": False},
        format="json",
    )

    assert resp.status_code == 200
    treatment.refresh_from_db()
    combo.refresh_from_db()
    assert treatment.is_active is False
    assert combo.is_active is False
    assert not PlacementItem.objects.filter(item_id=treatment.id).exists()
    assert not PlacementItem.objects.filter(item_id=combo.id).exists()


# ======================
# Combo signal tests
# ======================


@pytest.mark.django_db
def test_delete_combo_removes_its_placement_item():
    category = _make_category()
    combo = _make_combo(category)
    placement = _make_placement()
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    combo_id = combo.id
    combo.delete()

    assert not PlacementItem.objects.filter(item_id=combo_id).exists()


@pytest.mark.django_db
def test_deactivate_combo_removes_its_placement_item():
    category = _make_category()
    combo = _make_combo(category, is_active=True)
    placement = _make_placement()
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    deactivate_combos([combo.id])

    assert not PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_api_combo_deactivation_cleans_placement():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)
    placement = _make_placement()
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {"is_active": False},
        format="json",
    )

    assert resp.status_code == 200
    combo.refresh_from_db()
    assert combo.is_active is False
    assert not PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_no_placement_change_when_combo_stays_active():
    category = _make_category()
    combo = _make_combo(category, is_active=True)
    placement = _make_placement()
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    combo.title = "Updated title"
    combo.save(update_fields=["title"])

    assert PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_no_placement_change_when_combo_stays_inactive():
    category = _make_category()
    combo = _make_combo(category, is_active=False)
    placement = _make_placement()
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    combo.title = "Updated title"
    combo.save(update_fields=["title"])

    assert PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_combo_reactivation_does_not_add_to_placement():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)
    placement = _make_placement()

    assert not PlacementItem.objects.filter(item_id=combo.id).exists()

    combo.is_active = True
    combo.save(update_fields=["is_active"])

    # Reactivation should not auto-add to placement
    assert not PlacementItem.objects.filter(item_id=combo.id).exists()


# ==============================
# Multiple placements scenarios
# ==============================


@pytest.mark.django_db
def test_deactivate_treatment_removes_from_multiple_placements():
    category = _make_category()
    treatment = _make_treatment(category, is_active=True)
    placement_a = _make_placement()
    placement_b = _make_placement()
    _add_to_placement(placement_a, treatment, PlacementItem.ItemKind.TREATMENT)
    _add_to_placement(placement_b, treatment, PlacementItem.ItemKind.TREATMENT)

    deactivate_treatments([treatment.id])

    assert PlacementItem.objects.filter(item_id=treatment.id).count() == 0


@pytest.mark.django_db
def test_delete_combo_removes_from_multiple_placements():
    category = _make_category()
    combo = _make_combo(category)
    placement_a = _make_placement()
    placement_b = _make_placement()
    _add_to_placement(placement_a, combo, PlacementItem.ItemKind.COMBO)
    _add_to_placement(placement_b, combo, PlacementItem.ItemKind.COMBO)

    combo_id = combo.id
    combo.delete()

    assert PlacementItem.objects.filter(item_id=combo_id).count() == 0


# ======================================
# Non-interference with other items
# ======================================


@pytest.mark.django_db
def test_deactivate_treatment_does_not_affect_unrelated_placements():
    category = _make_category()
    treatment_a = _make_treatment(category, is_active=True)
    treatment_b = _make_treatment(category, is_active=True)
    combo = _make_combo(category, is_active=True)
    placement = _make_placement()
    _add_to_placement(placement, treatment_a, PlacementItem.ItemKind.TREATMENT)
    _add_to_placement(placement, treatment_b, PlacementItem.ItemKind.TREATMENT)
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    deactivate_treatments([treatment_a.id])

    assert not PlacementItem.objects.filter(item_id=treatment_a.id).exists()
    assert PlacementItem.objects.filter(item_id=treatment_b.id).exists()
    assert PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_deactivate_combo_does_not_affect_unrelated_placements():
    category = _make_category()
    treatment = _make_treatment(category)
    combo_a = _make_combo(category, is_active=True)
    combo_b = _make_combo(category, is_active=True)
    placement = _make_placement()
    _add_to_placement(placement, treatment, PlacementItem.ItemKind.TREATMENT)
    _add_to_placement(placement, combo_a, PlacementItem.ItemKind.COMBO)
    _add_to_placement(placement, combo_b, PlacementItem.ItemKind.COMBO)

    deactivate_combos([combo_a.id])

    assert not PlacementItem.objects.filter(item_id=combo_a.id).exists()
    assert PlacementItem.objects.filter(item_id=combo_b.id).exists()
    assert PlacementItem.objects.filter(item_id=treatment.id).exists()


# ========================================
# Combo via compact sessions (edge case)
# ========================================


@pytest.mark.django_db
def test_delete_last_ingredient_removes_combo_from_placement():
    """
    When the last ComboIngredient is deleted, the combo gets deactivated
    via _compact_combo_sessions. The placement cleanup should still happen.
    """
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)

    placement = _make_placement()
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    # Delete the last ingredient manually
    ingredient.delete()

    combo.refresh_from_db()
    assert combo.is_active is False
    assert not PlacementItem.objects.filter(item_id=combo.id).exists()


@pytest.mark.django_db
def test_delete_tzc_removes_combo_from_placement():
    """
    When a TreatmentZoneConfig is deleted and this empties a combo's ingredients,
    the combo should be removed from placements via the cascade flow.
    """
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)

    placement = _make_placement()
    _add_to_placement(placement, combo, PlacementItem.ItemKind.COMBO)

    tzc.delete()

    combo.refresh_from_db()
    assert combo.is_active is False
    assert not PlacementItem.objects.filter(item_id=combo.id).exists()

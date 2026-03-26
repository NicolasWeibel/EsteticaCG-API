import uuid
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from apps.catalog.admin.combo import ComboAdmin, ComboAdminForm
from apps.catalog.admin.treatment import TreatmentAdminForm
from apps.catalog.models import (
    Category,
    Combo,
    ComboIngredient,
    ComboSessionItem,
    Journey,
    Treatment,
    TreatmentZoneConfig,
    Zone,
)
from apps.catalog.serializers.combo import ComboSerializer
from apps.catalog.serializers.treatment import TreatmentSerializer
from apps.catalog.services.validation import (
    validate_combo_rules,
    validate_combo_treatments_active,
    validate_optional_gt_zero_or_null,
    validate_treatment_rules,
)
from apps.catalog.services.combo_sessions import (
    prune_session_items_for_sessions,
    serialize_session_items_for_validation,
)
from apps.catalog.services.commands import deactivate_treatments


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


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


def _make_journey(category: Category) -> Journey:
    return Journey.objects.create(
        slug=_uid("journey-slug"),
        title=_uid("Journey"),
        category=category,
    )


def _make_combo(
    category: Category, *, is_active: bool = True, sessions: int = 2
) -> Combo:
    return Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=200,
        sessions=sessions,
        is_active=is_active,
    )


@pytest.mark.django_db
def test_delete_zone_deactivates_combo_and_compacts_sessions():
    category = _make_category()
    zone_a = _make_zone(category)
    zone_b = _make_zone(category)
    treatment_a = _make_treatment(category)
    treatment_b = _make_treatment(category)
    tzc_a = TreatmentZoneConfig.objects.create(
        treatment=treatment_a,
        zone=zone_a,
        duration=30,
        price=100,
    )
    tzc_b = TreatmentZoneConfig.objects.create(
        treatment=treatment_b,
        zone=zone_b,
        duration=30,
        price=120,
    )
    combo = _make_combo(category, is_active=True, sessions=2)
    ing_a = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc_a)
    ing_b = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc_b)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ing_a)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ing_b)
    ComboSessionItem.objects.create(combo=combo, session_index=2, ingredient=ing_a)

    zone_a.delete()

    combo.refresh_from_db()
    assert combo.is_active is False
    assert combo.sessions == 1
    assert combo.ingredients.count() == 1
    assert combo.session_items.count() == 1
    assert combo.session_items.first().session_index == 1


@pytest.mark.django_db
def test_delete_treatment_zone_config_deactivates_combo():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ing = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ing)

    tzc.delete()

    combo.refresh_from_db()
    assert combo.is_active is False
    assert combo.sessions == 0
    assert combo.ingredients.count() == 0
    assert combo.session_items.count() == 0


@pytest.mark.django_db
def test_manual_ingredient_delete_keeps_combo_active_if_other_ingredients_remain():
    category = _make_category()
    zone_a = _make_zone(category)
    zone_b = _make_zone(category)
    treatment_a = _make_treatment(category)
    treatment_b = _make_treatment(category)
    tzc_a = TreatmentZoneConfig.objects.create(
        treatment=treatment_a,
        zone=zone_a,
        duration=30,
        price=100,
    )
    tzc_b = TreatmentZoneConfig.objects.create(
        treatment=treatment_b,
        zone=zone_b,
        duration=30,
        price=120,
    )
    combo = _make_combo(category, is_active=True, sessions=2)
    ing_a = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc_a)
    ing_b = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc_b)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ing_a)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ing_b)
    ComboSessionItem.objects.create(combo=combo, session_index=2, ingredient=ing_a)

    ing_a.delete()

    combo.refresh_from_db()
    assert combo.is_active is True
    assert combo.sessions == 1
    assert combo.ingredients.count() == 1
    assert combo.session_items.count() == 1


@pytest.mark.django_db
def test_manual_ingredient_delete_deactivates_combo_if_no_ingredients_remain():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ing = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ing)

    ing.delete()

    combo.refresh_from_db()
    assert combo.is_active is False
    assert combo.sessions == 0
    assert combo.ingredients.count() == 0
    assert combo.session_items.count() == 0


@pytest.mark.django_db
def test_delete_treatment_deactivates_combo_through_tzc_cascade():
    category = _make_category()
    zone_a = _make_zone(category)
    zone_b = _make_zone(category)
    treatment_a = _make_treatment(category)
    treatment_b = _make_treatment(category)
    tzc_a = TreatmentZoneConfig.objects.create(
        treatment=treatment_a,
        zone=zone_a,
        duration=30,
        price=100,
    )
    tzc_b = TreatmentZoneConfig.objects.create(
        treatment=treatment_b,
        zone=zone_b,
        duration=30,
        price=120,
    )
    combo = _make_combo(category, is_active=True, sessions=1)
    ing_a = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc_a)
    ing_b = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc_b)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ing_a)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ing_b)

    treatment_a.delete()

    combo.refresh_from_db()
    assert combo.is_active is False
    assert combo.ingredients.count() == 1
    assert combo.session_items.count() == 1


@pytest.mark.django_db
def test_delete_last_tzc_deactivates_treatment():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=True)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )

    tzc.delete()

    treatment.refresh_from_db()
    assert treatment.is_active is False


@pytest.mark.django_db
def test_remove_addon_only_impacts_combos_in_that_journey():
    category = _make_category()
    journey_x = _make_journey(category)
    journey_y = _make_journey(category)
    zone = _make_zone(category)

    addon_treatment = _make_treatment(category, is_active=True)
    addon_treatment.journey = journey_y
    addon_treatment.save(update_fields=["journey"])
    journey_x.addons.add(addon_treatment)

    tzc = TreatmentZoneConfig.objects.create(
        treatment=addon_treatment,
        zone=zone,
        duration=30,
        price=100,
    )

    combo_x = _make_combo(category, is_active=True, sessions=1)
    combo_x.journey = journey_x
    combo_x.save(update_fields=["journey"])
    ing_x = ComboIngredient.objects.create(combo=combo_x, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo_x, session_index=1, ingredient=ing_x)

    combo_y = _make_combo(category, is_active=True, sessions=1)
    combo_y.journey = journey_y
    combo_y.save(update_fields=["journey"])
    ing_y = ComboIngredient.objects.create(combo=combo_y, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo_y, session_index=1, ingredient=ing_y)

    journey_x.addons.remove(addon_treatment)

    combo_x.refresh_from_db()
    combo_y.refresh_from_db()
    assert combo_x.is_active is False
    assert combo_x.ingredients.count() == 0
    assert combo_x.session_items.count() == 0
    assert combo_y.is_active is True
    assert combo_y.ingredients.count() == 1
    assert combo_y.session_items.count() == 1


@pytest.mark.django_db
def test_clear_addons_removes_matching_ingredients_and_deactivates_combos():
    category = _make_category()
    journey_x = _make_journey(category)
    journey_y = _make_journey(category)
    zone_a = _make_zone(category)
    zone_b = _make_zone(category)

    addon_a = _make_treatment(category, is_active=True)
    addon_b = _make_treatment(category, is_active=True)
    addon_a.journey = journey_y
    addon_b.journey = journey_y
    addon_a.save(update_fields=["journey"])
    addon_b.save(update_fields=["journey"])
    journey_x.addons.add(addon_a, addon_b)

    tzc_a = TreatmentZoneConfig.objects.create(
        treatment=addon_a,
        zone=zone_a,
        duration=30,
        price=100,
    )
    tzc_b = TreatmentZoneConfig.objects.create(
        treatment=addon_b,
        zone=zone_b,
        duration=30,
        price=100,
    )

    combo_x = _make_combo(category, is_active=True, sessions=1)
    combo_x.journey = journey_x
    combo_x.save(update_fields=["journey"])
    ing_a = ComboIngredient.objects.create(combo=combo_x, treatment_zone_config=tzc_a)
    ing_b = ComboIngredient.objects.create(combo=combo_x, treatment_zone_config=tzc_b)
    ComboSessionItem.objects.create(combo=combo_x, session_index=1, ingredient=ing_a)
    ComboSessionItem.objects.create(combo=combo_x, session_index=1, ingredient=ing_b)

    journey_x.addons.clear()

    combo_x.refresh_from_db()
    assert combo_x.is_active is False
    assert combo_x.ingredients.count() == 0
    assert combo_x.session_items.count() == 0


@pytest.mark.django_db
def test_deactivate_treatment_deactivates_related_combos_without_deleting_data():
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

    deactivate_treatments([treatment.id])

    combo.refresh_from_db()
    assert combo.is_active is False
    assert combo.ingredients.count() == 1
    assert combo.session_items.count() == 1
    assert TreatmentZoneConfig.objects.filter(id=tzc.id).exists() is True


@pytest.mark.django_db
def test_prune_session_items_for_sessions_removes_out_of_range_items():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=4)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    item1 = ComboSessionItem.objects.create(
        combo=combo, session_index=1, ingredient=ingredient
    )
    item4 = ComboSessionItem.objects.create(
        combo=combo, session_index=4, ingredient=ingredient
    )

    deleted = prune_session_items_for_sessions(combo, sessions=3)

    assert deleted == 1
    assert ComboSessionItem.objects.filter(id=item1.id).exists() is True
    assert ComboSessionItem.objects.filter(id=item4.id).exists() is False


@pytest.mark.django_db
def test_prune_session_items_for_sessions_clears_all_when_sessions_zero():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=2)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)
    ComboSessionItem.objects.create(combo=combo, session_index=2, ingredient=ingredient)

    deleted = prune_session_items_for_sessions(combo, sessions=0)

    assert deleted == 2
    assert combo.session_items.count() == 0


@pytest.mark.django_db
def test_serialize_session_items_for_validation_shape():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)

    serialized = serialize_session_items_for_validation(combo.session_items.all())

    assert serialized == [{"session_index": 1, "ingredient": ingredient.id}]


def test_validate_combo_rules_allows_inactive_with_ingredients_and_no_sessions():
    validate_combo_rules(
        is_active=False,
        sessions=0,
        ingredient_ids=["ing-1"],
        session_items=[],
    )


def test_validate_combo_rules_rejects_active_with_zero_sessions():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=True,
            sessions=0,
            ingredient_ids=["ing-1"],
            session_items=[],
        )


def test_validate_combo_rules_rejects_session_items_when_sessions_zero():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=False,
            sessions=0,
            ingredient_ids=["ing-1"],
            session_items=[{"session_index": 1, "ingredient": "ing-1"}],
        )


def test_validate_combo_rules_rejects_missing_session_items_with_sessions_gt_zero():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=False,
            sessions=1,
            ingredient_ids=["ing-1"],
            session_items=None,
        )


def test_validate_combo_rules_rejects_no_ingredients_with_sessions_gt_zero():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=False,
            sessions=1,
            ingredient_ids=[],
            session_items=[],
        )


def test_validate_combo_rules_rejects_session_index_out_of_range():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=False,
            sessions=1,
            ingredient_ids=["ing-1"],
            session_items=[{"session_index": 2, "ingredient": "ing-1"}],
        )


def test_validate_combo_rules_rejects_ingredient_not_in_combo():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=False,
            sessions=1,
            ingredient_ids=["ing-1"],
            session_items=[{"session_index": 1, "ingredient": "ing-2"}],
        )


def test_validate_combo_rules_rejects_duplicate_ingredient_same_session():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=False,
            sessions=1,
            ingredient_ids=["ing-1"],
            session_items=[
                {"session_index": 1, "ingredient": "ing-1"},
                {"session_index": 1, "ingredient": "ing-1"},
            ],
        )


def test_validate_combo_rules_rejects_empty_sessions():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=False,
            sessions=2,
            ingredient_ids=["ing-1"],
            session_items=[{"session_index": 1, "ingredient": "ing-1"}],
        )


def test_validate_combo_rules_rejects_missing_ingredient_usage():
    with pytest.raises(ValidationError):
        validate_combo_rules(
            is_active=False,
            sessions=1,
            ingredient_ids=["ing-1", "ing-2"],
            session_items=[{"session_index": 1, "ingredient": "ing-1"}],
        )


def test_validate_treatment_rules_rejects_active_without_zones():
    with pytest.raises(ValidationError):
        validate_treatment_rules(
            is_active=True,
            requires_zones=True,
            has_zones=False,
        )


def test_validate_treatment_rules_allows_inactive_without_zones():
    validate_treatment_rules(
        is_active=False,
        requires_zones=True,
        has_zones=False,
    )


@pytest.mark.django_db
def test_validate_combo_treatments_active_rejects_active_combo_with_inactive_treatment():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=False)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )

    with pytest.raises(ValidationError):
        validate_combo_treatments_active(
            is_active=True,
            treatment_zone_config_ids=[tzc.id],
        )


@pytest.mark.django_db
def test_validate_combo_treatments_active_allows_inactive_combo():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=False)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )

    validate_combo_treatments_active(
        is_active=False,
        treatment_zone_config_ids=[tzc.id],
    )


def test_validate_optional_gt_zero_or_null_rejects_zero():
    with pytest.raises(ValidationError):
        validate_optional_gt_zero_or_null(
            field_name="duration",
            value=0,
        )


def test_validate_optional_gt_zero_or_null_allows_null_and_positive():
    validate_optional_gt_zero_or_null(field_name="duration", value=None)
    validate_optional_gt_zero_or_null(field_name="duration", value=1)


@pytest.mark.django_db
def test_combo_serializer_rejects_slug_used_by_treatment():
    category = _make_category()
    treatment = _make_treatment(category)
    combo = _make_combo(category, is_active=False, sessions=0)

    serializer = ComboSerializer(
        instance=combo,
        data={"slug": treatment.slug},
        partial=True,
    )

    assert serializer.is_valid() is False
    assert serializer.errors["slug"] == [
        "Ya existe Treatment con este Slug en esta categoría."
    ]


@pytest.mark.django_db
def test_treatment_serializer_rejects_slug_used_by_combo():
    category = _make_category()
    combo = _make_combo(category)
    treatment = _make_treatment(category)

    serializer = TreatmentSerializer(
        instance=treatment,
        data={"slug": combo.slug},
        partial=True,
    )

    assert serializer.is_valid() is False
    assert serializer.errors["slug"] == [
        "Ya existe Combo con este Slug en esta categoría."
    ]


@pytest.mark.django_db
def test_combo_admin_form_rejects_active_with_zero_sessions():
    category = _make_category()
    form = ComboAdminForm(
        data={
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "100",
            "sessions": "0",
            "is_active": "on",
            "session_freq": "week",
            "session_interval": "1",
            "occurrences_per_period": "1",
            "order": "0",
            "comboingredient_set-TOTAL_FORMS": "0",
            "comboingredient_set-INITIAL_FORMS": "0",
            "comboingredient_set-MIN_NUM_FORMS": "0",
            "comboingredient_set-MAX_NUM_FORMS": "1000",
            "combosessionitem_set-TOTAL_FORMS": "0",
            "combosessionitem_set-INITIAL_FORMS": "0",
            "combosessionitem_set-MIN_NUM_FORMS": "0",
            "combosessionitem_set-MAX_NUM_FORMS": "1000",
        }
    )

    assert form.is_valid() is False
    assert "sessions" in form.errors


def _combo_admin_update_payload(combo, ingredient, session_item, *, is_active):
    payload = {
        "slug": combo.slug,
        "title": combo.title,
        "category": str(combo.category_id),
        "price": str(combo.price),
        "sessions": str(combo.sessions),
        "min_session_interval_days": str(combo.min_session_interval_days),
        "session_freq": combo.session_freq,
        "session_interval": str(combo.session_interval),
        "occurrences_per_period": str(combo.occurrences_per_period),
        "order": str(combo.order),
        "comboingredient_set-TOTAL_FORMS": "1",
        "comboingredient_set-INITIAL_FORMS": "1",
        "comboingredient_set-MIN_NUM_FORMS": "0",
        "comboingredient_set-MAX_NUM_FORMS": "1000",
        "comboingredient_set-0-id": str(ingredient.id),
        "comboingredient_set-0-combo": str(combo.id),
        "comboingredient_set-0-treatment_zone_config": str(
            ingredient.treatment_zone_config_id
        ),
        "combosessionitem_set-TOTAL_FORMS": "1",
        "combosessionitem_set-INITIAL_FORMS": "1",
        "combosessionitem_set-MIN_NUM_FORMS": "0",
        "combosessionitem_set-MAX_NUM_FORMS": "1000",
        "combosessionitem_set-0-id": str(session_item.id),
        "combosessionitem_set-0-combo": str(combo.id),
        "combosessionitem_set-0-session_index": str(session_item.session_index),
        "combosessionitem_set-0-ingredient": str(ingredient.id),
    }
    if is_active:
        payload["is_active"] = "on"
    return payload


def _combo_admin_update_payload_with_session_rows(
    combo,
    ingredient,
    *,
    sessions,
    is_active,
    session_rows,
):
    payload = {
        "slug": combo.slug,
        "title": combo.title,
        "category": str(combo.category_id),
        "price": str(combo.price),
        "sessions": str(sessions),
        "min_session_interval_days": str(combo.min_session_interval_days),
        "session_freq": combo.session_freq,
        "session_interval": str(combo.session_interval),
        "occurrences_per_period": str(combo.occurrences_per_period),
        "order": str(combo.order),
        "comboingredient_set-TOTAL_FORMS": "1",
        "comboingredient_set-INITIAL_FORMS": "1",
        "comboingredient_set-MIN_NUM_FORMS": "0",
        "comboingredient_set-MAX_NUM_FORMS": "1000",
        "comboingredient_set-0-id": str(ingredient.id),
        "comboingredient_set-0-combo": str(combo.id),
        "comboingredient_set-0-treatment_zone_config": str(
            ingredient.treatment_zone_config_id
        ),
        "combosessionitem_set-TOTAL_FORMS": str(len(session_rows)),
        "combosessionitem_set-INITIAL_FORMS": str(
            len([row for row in session_rows if row.get("id")])
        ),
        "combosessionitem_set-MIN_NUM_FORMS": "0",
        "combosessionitem_set-MAX_NUM_FORMS": "1000",
    }
    if is_active:
        payload["is_active"] = "on"

    for idx, row in enumerate(session_rows):
        if row.get("id"):
            payload[f"combosessionitem_set-{idx}-id"] = str(row["id"])
        payload[f"combosessionitem_set-{idx}-combo"] = str(combo.id)
        payload[f"combosessionitem_set-{idx}-session_index"] = str(
            row["session_index"]
        )
        payload[f"combosessionitem_set-{idx}-ingredient"] = str(
            row.get("ingredient", ingredient.id)
        )
        if row.get("delete"):
            payload[f"combosessionitem_set-{idx}-DELETE"] = "on"
    return payload


@pytest.mark.django_db
def test_combo_admin_form_rejects_activate_with_inactive_treatment():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=False)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    session_item = ComboSessionItem.objects.create(
        combo=combo, session_index=1, ingredient=ingredient
    )

    form = ComboAdminForm(
        instance=combo,
        data=_combo_admin_update_payload(
            combo, ingredient, session_item, is_active=True
        ),
    )

    assert form.is_valid() is False
    assert "is_active" in form.errors


@pytest.mark.django_db
def test_combo_admin_form_rejects_activate_with_inactive_treatment_using_related_name_prefixes():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=False)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    session_item = ComboSessionItem.objects.create(
        combo=combo, session_index=1, ingredient=ingredient
    )

    form = ComboAdminForm(
        instance=combo,
        data={
            "slug": combo.slug,
            "title": combo.title,
            "category": str(combo.category_id),
            "price": str(combo.price),
            "sessions": str(combo.sessions),
            "min_session_interval_days": str(combo.min_session_interval_days),
            "session_freq": combo.session_freq,
            "session_interval": str(combo.session_interval),
            "occurrences_per_period": str(combo.occurrences_per_period),
            "order": str(combo.order),
            "is_active": "on",
            "ingredients-TOTAL_FORMS": "1",
            "ingredients-INITIAL_FORMS": "1",
            "ingredients-MIN_NUM_FORMS": "0",
            "ingredients-MAX_NUM_FORMS": "1000",
            "ingredients-0-id": str(ingredient.id),
            "ingredients-0-combo": str(combo.id),
            "ingredients-0-treatment_zone_config": str(
                ingredient.treatment_zone_config_id
            ),
            "session_items-TOTAL_FORMS": "1",
            "session_items-INITIAL_FORMS": "1",
            "session_items-MIN_NUM_FORMS": "0",
            "session_items-MAX_NUM_FORMS": "1000",
            "session_items-0-id": str(session_item.id),
            "session_items-0-combo": str(combo.id),
            "session_items-0-session_index": str(session_item.session_index),
            "session_items-0-ingredient": str(ingredient.id),
        },
    )

    assert form.is_valid() is False
    assert "is_active" in form.errors


@pytest.mark.django_db
def test_combo_admin_form_allows_inactive_with_inactive_treatment():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category, is_active=False)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=1)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    session_item = ComboSessionItem.objects.create(
        combo=combo, session_index=1, ingredient=ingredient
    )

    form = ComboAdminForm(
        instance=combo,
        data=_combo_admin_update_payload(
            combo, ingredient, session_item, is_active=False
        ),
    )

    assert form.is_valid() is True


@pytest.mark.django_db
def test_combo_admin_form_allows_reduce_sessions_with_legacy_out_of_range_rows():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=4)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    s1 = ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)
    s2 = ComboSessionItem.objects.create(combo=combo, session_index=2, ingredient=ingredient)
    s3 = ComboSessionItem.objects.create(combo=combo, session_index=3, ingredient=ingredient)
    s4 = ComboSessionItem.objects.create(combo=combo, session_index=4, ingredient=ingredient)

    form = ComboAdminForm(
        instance=combo,
        data=_combo_admin_update_payload_with_session_rows(
            combo,
            ingredient,
            sessions=3,
            is_active=False,
            session_rows=[
                {"id": s1.id, "session_index": 1},
                {"id": s2.id, "session_index": 2},
                {"id": s3.id, "session_index": 3},
                {"id": s4.id, "session_index": 4},
            ],
        ),
    )

    assert form.is_valid() is True


@pytest.mark.django_db
def test_combo_admin_form_rejects_manual_out_of_range_row_on_reduce_sessions():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=4)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    s1 = ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)
    s2 = ComboSessionItem.objects.create(combo=combo, session_index=2, ingredient=ingredient)
    s3 = ComboSessionItem.objects.create(combo=combo, session_index=3, ingredient=ingredient)

    form = ComboAdminForm(
        instance=combo,
        data=_combo_admin_update_payload_with_session_rows(
            combo,
            ingredient,
            sessions=3,
            is_active=False,
            session_rows=[
                {"id": s1.id, "session_index": 1},
                {"id": s2.id, "session_index": 2},
                {"id": s3.id, "session_index": 3},
                {"session_index": 4},
            ],
        ),
    )

    assert form.is_valid() is False
    assert "__all__" in form.errors


@pytest.mark.django_db
def test_combo_admin_save_related_prunes_session_items_over_sessions():
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = _make_combo(category, is_active=False, sessions=3)
    ingredient = ComboIngredient.objects.create(combo=combo, treatment_zone_config=tzc)
    ComboSessionItem.objects.create(combo=combo, session_index=1, ingredient=ingredient)
    ComboSessionItem.objects.create(combo=combo, session_index=4, ingredient=ingredient)

    combo_admin = ComboAdmin(Combo, AdminSite())
    request = RequestFactory().post("/admin/catalog/combo/")
    form = SimpleNamespace(instance=combo, save_m2m=lambda: None)

    with mock.patch(
        "django.contrib.admin.options.ModelAdmin.save_related", autospec=True
    ) as patched_super:
        combo_admin.save_related(request, form, [], change=True)
        patched_super.assert_called_once()

    assert combo.session_items.filter(session_index=4).exists() is False
    assert combo.session_items.filter(session_index=1).exists() is True


@pytest.mark.django_db
def test_combo_admin_form_rejects_duration_zero():
    category = _make_category()
    form = ComboAdminForm(
        data={
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "100",
            "sessions": "0",
            "duration": "0",
            "min_session_interval_days": "0",
            "session_freq": "week",
            "session_interval": "1",
            "occurrences_per_period": "1",
            "order": "0",
            "comboingredient_set-TOTAL_FORMS": "0",
            "comboingredient_set-INITIAL_FORMS": "0",
            "comboingredient_set-MIN_NUM_FORMS": "0",
            "comboingredient_set-MAX_NUM_FORMS": "1000",
            "combosessionitem_set-TOTAL_FORMS": "0",
            "combosessionitem_set-INITIAL_FORMS": "0",
            "combosessionitem_set-MIN_NUM_FORMS": "0",
            "combosessionitem_set-MAX_NUM_FORMS": "1000",
        }
    )

    assert form.is_valid() is False
    assert "duration" in form.errors


@pytest.mark.django_db
def test_treatment_admin_form_rejects_active_without_zone_configs():
    category = _make_category()
    form = TreatmentAdminForm(
        data={
            "slug": _uid("treat-slug"),
            "title": _uid("Treatment"),
            "category": str(category.id),
            "is_active": "on",
            "requires_zones": "on",
            "order": "0",
            "treatmentzoneconfig_set-TOTAL_FORMS": "0",
            "treatmentzoneconfig_set-INITIAL_FORMS": "0",
            "treatmentzoneconfig_set-MIN_NUM_FORMS": "0",
            "treatmentzoneconfig_set-MAX_NUM_FORMS": "1000",
        }
    )

    assert form.is_valid() is False
    assert "__all__" in form.errors


@pytest.mark.django_db
def test_treatment_admin_form_allows_active_with_related_name_zone_prefix():
    category = _make_category()
    zone = _make_zone(category)
    form = TreatmentAdminForm(
        data={
            "slug": _uid("treat-slug"),
            "title": _uid("Treatment"),
            "category": str(category.id),
            "is_active": "on",
            "requires_zones": "on",
            "order": "0",
            "zone_configs-TOTAL_FORMS": "1",
            "zone_configs-INITIAL_FORMS": "0",
            "zone_configs-MIN_NUM_FORMS": "0",
            "zone_configs-MAX_NUM_FORMS": "1000",
            "zone_configs-0-zone": str(zone.id),
            "zone_configs-0-duration": "30",
            "zone_configs-0-price": "100",
            "zone_configs-0-promotional_price": "",
            "zone_configs-0-body_position": "",
        }
    )

    assert form.is_valid() is True

import uuid

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.admin.combo import ComboAdminForm
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
    validate_treatment_rules,
)


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

    treatment.is_active = False
    treatment.save(update_fields=["is_active"])

    combo.refresh_from_db()
    assert combo.is_active is False
    assert combo.ingredients.count() == 1
    assert combo.session_items.count() == 1
    assert TreatmentZoneConfig.objects.filter(id=tzc.id).exists() is True


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
    assert "slug" in serializer.errors


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
    assert "slug" in serializer.errors


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

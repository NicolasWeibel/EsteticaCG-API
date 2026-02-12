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
    Treatment,
    TreatmentZoneConfig,
    Zone,
)
from apps.catalog.serializers.combo import ComboSerializer
from apps.catalog.serializers.treatment import TreatmentSerializer
from apps.catalog.services.validation import (
    validate_combo_rules,
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

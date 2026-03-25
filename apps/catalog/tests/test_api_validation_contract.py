import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.catalog.models import (
    Category,
    Combo,
    Journey,
    Treatment,
    TreatmentZoneConfig,
    Zone,
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


def _make_treatment(category: Category) -> Treatment:
    return Treatment.objects.create(
        category=category,
        slug=_uid("treat-slug"),
        title=_uid("Treatment"),
    )


def _make_journey(category: Category) -> Journey:
    return Journey.objects.create(
        category=category,
        slug=_uid("journey-slug"),
        title=_uid("Journey"),
    )


def _combo_put_payload(combo: Combo, category: Category, **overrides):
    payload = {
        "slug": combo.slug,
        "title": combo.title,
        "category": str(category.id),
        "price": str(combo.price),
        "is_active": combo.is_active,
        "sessions": combo.sessions,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_api_combo_rejects_active_with_zero_sessions():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": True,
            "sessions": 0,
            "session_items": [],
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["sessions"] == ["sessions no puede ser 0 si el combo está activo."]


@pytest.mark.django_db
def test_api_combo_rejects_session_items_when_sessions_is_zero():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": False,
            "sessions": 0,
            "ingredients": [{"treatment_zone_config": str(tzc.id)}],
            "session_items": [
                {"session_index": 1, "treatment_zone_config": str(tzc.id)}
            ],
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["session_items"] == ["session_items no es válido si sessions es 0."]


@pytest.mark.django_db
def test_api_combo_rejects_duration_zero():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": False,
            "sessions": 0,
            "duration": 0,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["duration"] == ["duration debe ser mayor a 0 o null."]


@pytest.mark.django_db
def test_api_combo_accepts_recurrence_fields():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": False,
            "sessions": 0,
            "session_freq": "month",
            "session_interval": 2,
            "occurrences_per_period": 1,
        },
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["session_freq"] == "month"
    assert resp.data["session_interval"] == 2
    assert resp.data["occurrences_per_period"] == 1


@pytest.mark.django_db
def test_api_combo_rejects_invalid_session_freq():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": False,
            "sessions": 0,
            "session_freq": "day",
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "session_freq" in resp.data


@pytest.mark.django_db
def test_api_combo_rejects_session_interval_zero():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": False,
            "sessions": 0,
            "session_interval": 0,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "session_interval" in resp.data


@pytest.mark.django_db
def test_api_combo_rejects_occurrences_per_period_zero():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": False,
            "sessions": 0,
            "occurrences_per_period": 0,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "occurrences_per_period" in resp.data


@pytest.mark.django_db
def test_api_combo_allows_inactive_with_ingredients_and_no_sessions():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": False,
            "sessions": 0,
            "ingredients": [{"treatment_zone_config": str(tzc.id)}],
        },
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["is_active"] is False
    assert resp.data["sessions"] == 0


@pytest.mark.django_db
def test_api_combo_rejects_slug_used_by_treatment():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    treatment = _make_treatment(category)

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": treatment.slug,
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": False,
            "sessions": 0,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["slug"] == [
        "Ya existe Treatment con este Slug en esta categoría."
    ]


@pytest.mark.django_db
def test_api_treatment_rejects_slug_used_by_combo():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=0,
    )

    resp = client.post(
        "/api/v1/catalog/treatments/",
        {
            "slug": combo.slug,
            "title": _uid("Treatment"),
            "category": str(category.id),
            "is_active": False,
            "requires_zones": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["slug"] == ["Ya existe Combo con este Slug en esta categoría."]


@pytest.mark.django_db
def test_api_treatment_rejects_active_without_zone_configs():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()

    resp = client.post(
        "/api/v1/catalog/treatments/",
        {
            "slug": _uid("treat-slug"),
            "title": _uid("Treatment"),
            "category": str(category.id),
            "is_active": True,
            "requires_zones": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["zone_configs"] == [
        "Este tratamiento requiere al menos una zona configurada."
    ]


@pytest.mark.django_db
def test_api_combo_rejects_active_with_inactive_treatment():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    treatment.is_active = False
    treatment.save(update_fields=["is_active"])
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )

    resp = client.post(
        "/api/v1/catalog/combos/",
        {
            "slug": _uid("combo-slug"),
            "title": _uid("Combo"),
            "category": str(category.id),
            "price": "120.00",
            "is_active": True,
            "sessions": 1,
            "ingredients": [{"treatment_zone_config": str(tzc.id)}],
            "session_items": [
                {"session_index": 1, "treatment_zone_config": str(tzc.id)}
            ],
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "is_active" in resp.data


@pytest.mark.django_db
def test_api_combo_update_rejects_reactivation_with_inactive_treatment():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=1,
    )
    ingredient = combo.ingredients.create(treatment_zone_config=tzc)
    combo.session_items.create(session_index=1, ingredient=ingredient)
    treatment.is_active = False
    treatment.save(update_fields=["is_active"])

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {"is_active": True},
        format="json",
    )

    assert resp.status_code == 400
    assert "is_active" in resp.data


@pytest.mark.django_db
def test_api_combo_update_prunes_items_when_sessions_reduced_without_session_items():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=4,
    )
    ingredient = combo.ingredients.create(treatment_zone_config=tzc)
    combo.session_items.create(session_index=1, ingredient=ingredient)
    combo.session_items.create(session_index=2, ingredient=ingredient)
    combo.session_items.create(session_index=3, ingredient=ingredient)
    combo.session_items.create(session_index=4, ingredient=ingredient)

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {"sessions": 3},
        format="json",
    )

    assert resp.status_code == 200
    combo.refresh_from_db()
    assert combo.sessions == 3
    assert combo.session_items.filter(session_index=4).exists() is False
    assert combo.session_items.count() == 3


@pytest.mark.django_db
def test_api_combo_update_prunes_all_items_when_sessions_set_to_zero_without_session_items():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=2,
    )
    ingredient = combo.ingredients.create(treatment_zone_config=tzc)
    combo.session_items.create(session_index=1, ingredient=ingredient)
    combo.session_items.create(session_index=2, ingredient=ingredient)

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {"sessions": 0},
        format="json",
    )

    assert resp.status_code == 200
    combo.refresh_from_db()
    assert combo.sessions == 0
    assert combo.session_items.count() == 0


@pytest.mark.django_db
def test_api_combo_update_rejects_explicit_out_of_range_session_items_when_sessions_reduced():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=4,
    )
    ingredient = combo.ingredients.create(treatment_zone_config=tzc)
    combo.session_items.create(session_index=1, ingredient=ingredient)
    combo.session_items.create(session_index=2, ingredient=ingredient)
    combo.session_items.create(session_index=3, ingredient=ingredient)
    combo.session_items.create(session_index=4, ingredient=ingredient)

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {
            "sessions": 3,
            "session_items": [
                {"session_index": 1, "treatment_zone_config": str(tzc.id)},
                {"session_index": 2, "treatment_zone_config": str(tzc.id)},
                {"session_index": 3, "treatment_zone_config": str(tzc.id)},
                {"session_index": 4, "treatment_zone_config": str(tzc.id)},
            ],
        },
        format="json",
    )

    assert resp.status_code == 400
    assert str(resp.data["session_items"]) == "session_index inválido: 4."


@pytest.mark.django_db
def test_api_combo_update_reducing_sessions_rolls_back_prune_if_ingredient_becomes_orphan():
    client = APIClient()
    client.force_authenticate(_make_staff())
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
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=4,
    )
    ing_a = combo.ingredients.create(treatment_zone_config=tzc_a)
    ing_b = combo.ingredients.create(treatment_zone_config=tzc_b)
    combo.session_items.create(session_index=1, ingredient=ing_a)
    combo.session_items.create(session_index=2, ingredient=ing_a)
    combo.session_items.create(session_index=3, ingredient=ing_a)
    session4 = combo.session_items.create(session_index=4, ingredient=ing_b)

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {"sessions": 3},
        format="json",
    )

    assert resp.status_code == 400
    assert (
        str(resp.data["session_items"])
        == "Cada ingrediente debe estar en al menos una sesión."
    )
    assert combo.session_items.filter(id=session4.id).exists() is True


@pytest.mark.django_db
def test_api_combo_put_without_ingredients_clears_ingredients_sessions_and_items():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=2,
    )
    ingredient = combo.ingredients.create(treatment_zone_config=tzc)
    combo.session_items.create(session_index=1, ingredient=ingredient)
    combo.session_items.create(session_index=2, ingredient=ingredient)

    payload = _combo_put_payload(combo, category, sessions=2)
    resp = client.put(
        f"/api/v1/catalog/combos/{combo.id}/",
        payload,
        format="json",
    )

    assert resp.status_code == 200
    combo.refresh_from_db()
    assert combo.is_active is False
    assert combo.sessions == 0
    assert combo.ingredients.count() == 0
    assert combo.session_items.count() == 0


@pytest.mark.django_db
def test_api_combo_patch_without_ingredients_keeps_existing_ingredients():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=1,
    )
    ingredient = combo.ingredients.create(treatment_zone_config=tzc)
    combo.session_items.create(session_index=1, ingredient=ingredient)

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {"title": _uid("Combo Updated")},
        format="json",
    )

    assert resp.status_code == 200
    combo.refresh_from_db()
    assert combo.ingredients.count() == 1
    assert combo.session_items.count() == 1


@pytest.mark.django_db
def test_api_combo_patch_syncs_ingredients_by_difference():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone_a = _make_zone(category)
    zone_b = _make_zone(category)
    zone_c = _make_zone(category)
    treatment_a = _make_treatment(category)
    treatment_b = _make_treatment(category)
    treatment_c = _make_treatment(category)
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
        price=100,
    )
    tzc_c = TreatmentZoneConfig.objects.create(
        treatment=treatment_c,
        zone=zone_c,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=1,
    )
    ing_a = combo.ingredients.create(treatment_zone_config=tzc_a)
    ing_b = combo.ingredients.create(treatment_zone_config=tzc_b)
    combo.session_items.create(session_index=1, ingredient=ing_a)
    combo.session_items.create(session_index=1, ingredient=ing_b)

    no_change = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {
            "ingredients": [
                {"treatment_zone_config": str(tzc_a.id)},
                {"treatment_zone_config": str(tzc_b.id)},
            ],
            "session_items": [
                {"session_index": 1, "treatment_zone_config": str(tzc_a.id)},
                {"session_index": 1, "treatment_zone_config": str(tzc_b.id)},
            ],
        },
        format="json",
    )
    assert no_change.status_code == 200
    combo.refresh_from_db()
    assert set(
        combo.ingredients.values_list("treatment_zone_config_id", flat=True)
    ) == {tzc_a.id, tzc_b.id}

    add_new = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {
            "ingredients": [
                {"treatment_zone_config": str(tzc_a.id)},
                {"treatment_zone_config": str(tzc_b.id)},
                {"treatment_zone_config": str(tzc_c.id)},
            ],
            "session_items": [
                {"session_index": 1, "treatment_zone_config": str(tzc_a.id)},
                {"session_index": 1, "treatment_zone_config": str(tzc_b.id)},
                {"session_index": 1, "treatment_zone_config": str(tzc_c.id)},
            ],
        },
        format="json",
    )
    assert add_new.status_code == 200
    combo.refresh_from_db()
    assert set(
        combo.ingredients.values_list("treatment_zone_config_id", flat=True)
    ) == {tzc_a.id, tzc_b.id, tzc_c.id}

    replace_mix = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {
            "ingredients": [
                {"treatment_zone_config": str(tzc_b.id)},
                {"treatment_zone_config": str(tzc_c.id)},
            ],
            "session_items": [
                {"session_index": 1, "treatment_zone_config": str(tzc_b.id)},
                {"session_index": 1, "treatment_zone_config": str(tzc_c.id)},
            ],
        },
        format="json",
    )
    assert replace_mix.status_code == 200
    combo.refresh_from_db()
    assert set(
        combo.ingredients.values_list("treatment_zone_config_id", flat=True)
    ) == {tzc_b.id, tzc_c.id}


@pytest.mark.django_db
def test_api_combo_patch_empty_ingredients_clears_sessions_and_items():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=1,
    )
    ingredient = combo.ingredients.create(treatment_zone_config=tzc)
    combo.session_items.create(session_index=1, ingredient=ingredient)

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {"ingredients": []},
        format="json",
    )

    assert resp.status_code == 200
    combo.refresh_from_db()
    assert combo.is_active is False
    assert combo.sessions == 0
    assert combo.ingredients.count() == 0
    assert combo.session_items.count() == 0


@pytest.mark.django_db
def test_api_combo_put_same_ingredients_keeps_sessions_and_session_items():
    client = APIClient()
    client.force_authenticate(_make_staff())
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
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=2,
    )
    ing_a = combo.ingredients.create(treatment_zone_config=tzc_a)
    ing_b = combo.ingredients.create(treatment_zone_config=tzc_b)
    combo.session_items.create(session_index=1, ingredient=ing_a)
    combo.session_items.create(session_index=2, ingredient=ing_b)

    payload = _combo_put_payload(
        combo,
        category,
        sessions=2,
        ingredients=[
            {"treatment_zone_config": str(tzc_a.id)},
            {"treatment_zone_config": str(tzc_b.id)},
        ],
        session_items=[
            {"session_index": 1, "treatment_zone_config": str(tzc_a.id)},
            {"session_index": 2, "treatment_zone_config": str(tzc_b.id)},
        ],
    )
    resp = client.put(
        f"/api/v1/catalog/combos/{combo.id}/",
        payload,
        format="json",
    )

    assert resp.status_code == 200
    combo.refresh_from_db()
    assert combo.sessions == 2
    assert combo.is_active is False
    assert combo.session_items.count() == 2


@pytest.mark.django_db
def test_api_combo_patch_rejects_duplicate_treatment_zone_configs_in_ingredients():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    zone = _make_zone(category)
    treatment = _make_treatment(category)
    tzc = TreatmentZoneConfig.objects.create(
        treatment=treatment,
        zone=zone,
        duration=30,
        price=100,
    )
    combo = Combo.objects.create(
        category=category,
        slug=_uid("combo-slug"),
        title=_uid("Combo"),
        price=100,
        is_active=False,
        sessions=1,
    )
    ingredient = combo.ingredients.create(treatment_zone_config=tzc)
    combo.session_items.create(session_index=1, ingredient=ingredient)

    resp = client.patch(
        f"/api/v1/catalog/combos/{combo.id}/",
        {
            "ingredients": [
                {"treatment_zone_config": str(tzc.id)},
                {"treatment_zone_config": str(tzc.id)},
            ],
        },
        format="json",
    )

    assert resp.status_code == 400
    assert str(resp.data["ingredients"]) == "No se permiten treatment_zone_config repetidos."


@pytest.mark.django_db
def test_category_items_excludes_inactive_treatments_and_combos():
    client = APIClient()
    category = _make_category()
    _make_treatment(category)
    inactive_treatment = _make_treatment(category)
    inactive_treatment.is_active = False
    inactive_treatment.save(update_fields=["is_active"])

    Combo.objects.create(
        category=category,
        slug=_uid("combo-active"),
        title=_uid("Combo Active"),
        price=100,
        is_active=True,
        sessions=1,
    )
    Combo.objects.create(
        category=category,
        slug=_uid("combo-inactive"),
        title=_uid("Combo Inactive"),
        price=100,
        is_active=False,
        sessions=0,
    )

    resp = client.get(f"/api/v1/catalog/categories/{category.id}/items/")
    assert resp.status_code == 200
    kinds = [item["kind"] for item in resp.data["items"]]
    assert kinds.count("treatment") == 1
    assert kinds.count("combo") == 1


@pytest.mark.django_db
def test_journey_items_excludes_inactive_treatments_and_combos():
    client = APIClient()
    category = _make_category()
    journey = _make_journey(category)

    Treatment.objects.create(
        category=category,
        journey=journey,
        slug=_uid("treat-active"),
        title=_uid("Treat Active"),
        is_active=True,
    )
    Treatment.objects.create(
        category=category,
        journey=journey,
        slug=_uid("treat-inactive"),
        title=_uid("Treat Inactive"),
        is_active=False,
    )
    Combo.objects.create(
        category=category,
        journey=journey,
        slug=_uid("combo-active"),
        title=_uid("Combo Active"),
        price=100,
        is_active=True,
        sessions=1,
    )
    Combo.objects.create(
        category=category,
        journey=journey,
        slug=_uid("combo-inactive"),
        title=_uid("Combo Inactive"),
        price=100,
        is_active=False,
        sessions=0,
    )

    resp = client.get(f"/api/v1/catalog/journeys/{journey.id}/items/")
    assert resp.status_code == 200
    kinds = [item["kind"] for item in resp.data["items"]]
    assert kinds.count("treatment") == 1
    assert kinds.count("combo") == 1


@pytest.mark.django_db
def test_api_journey_patch_supports_nested_benefits_recommended_points_and_faqs():
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    journey = _make_journey(category)

    benefit_keep = journey.benefits.create(
        title="B vieja",
        detail="Detalle viejo",
        order=0,
    )
    benefit_remove = journey.benefits.create(
        title="B borrar",
        detail="Detalle borrar",
        order=1,
    )
    rec_keep = journey.recommended_points.create(
        title="R vieja",
        detail="Detalle viejo",
        order=0,
    )
    faq_keep = journey.faqs.create(
        question="Q vieja",
        answer="A vieja",
        order=0,
    )
    faq_remove = journey.faqs.create(
        question="Q borrar",
        answer="A borrar",
        order=1,
    )

    resp = client.patch(
        f"/api/v1/catalog/journeys/{journey.id}/",
        {
            "benefits": [
                {
                    "id": str(benefit_keep.id),
                    "title": "B actualizada",
                    "detail": "Detalle actualizado",
                    "order": 0,
                },
                {"title": "B nueva", "detail": "Detalle nueva", "order": 1},
            ],
            "benefits_remove_ids": [str(benefit_remove.id)],
            "recommended_points": [
                {
                    "id": str(rec_keep.id),
                    "title": "R actualizada",
                    "detail": "Detalle actualizado",
                    "order": 0,
                },
                {"title": "R nueva", "detail": "Detalle nueva", "order": 1},
            ],
            "faqs": [
                {
                    "id": str(faq_keep.id),
                    "question": "Q actualizada",
                    "answer": "A actualizada",
                    "order": 0,
                },
                {"question": "Q nueva", "answer": "A nueva", "order": 1},
            ],
            "faqs_remove_ids": [str(faq_remove.id)],
        },
        format="json",
    )

    assert resp.status_code == 200

    journey.refresh_from_db()
    benefits = list(journey.benefits.order_by("order", "id"))
    assert [item.title for item in benefits] == ["B actualizada", "B nueva"]
    assert [item.order for item in benefits] == [0, 1]

    recommended_points = list(journey.recommended_points.order_by("order", "id"))
    assert [item.title for item in recommended_points] == ["R actualizada", "R nueva"]
    assert [item.order for item in recommended_points] == [0, 1]

    faqs = list(journey.faqs.order_by("order", "id"))
    assert [item.question for item in faqs] == ["Q actualizada", "Q nueva"]
    assert [item.order for item in faqs] == [0, 1]

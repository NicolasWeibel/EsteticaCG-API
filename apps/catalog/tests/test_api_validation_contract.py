import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.catalog.models import Category, Combo, Treatment, TreatmentZoneConfig, Zone


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
    assert resp.data["slug"] == ["El slug ya está en uso por un tratamiento."]


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
    assert resp.data["slug"] == ["El slug ya está en uso por un combo."]


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

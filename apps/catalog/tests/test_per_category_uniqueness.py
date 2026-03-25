import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.catalog.serializers.journey import JourneySerializer
from apps.catalog.models import Category, Combo, Journey, Treatment


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


def _journey_payload(category: Category, **overrides):
    payload = {
        "slug": _uid("journey-slug"),
        "title": _uid("Journey"),
        "category": str(category.id),
    }
    payload.update(overrides)
    return payload


def _treatment_payload(category: Category, **overrides):
    payload = {
        "slug": _uid("treatment-slug"),
        "title": _uid("Treatment"),
        "category": str(category.id),
        "is_active": False,
        "requires_zones": False,
    }
    payload.update(overrides)
    return payload


def _combo_payload(category: Category, **overrides):
    payload = {
        "slug": _uid("combo-slug"),
        "title": _uid("Combo"),
        "category": str(category.id),
        "price": "120.00",
        "is_active": False,
        "sessions": 0,
    }
    payload.update(overrides)
    return payload


def _make_journey(category: Category, **overrides) -> Journey:
    defaults = {
        "slug": _uid("journey-slug"),
        "title": _uid("Journey"),
        "category": category,
    }
    defaults.update(overrides)
    return Journey.objects.create(**defaults)


def _make_treatment(category: Category, **overrides) -> Treatment:
    defaults = {
        "slug": _uid("treatment-slug"),
        "title": _uid("Treatment"),
        "category": category,
        "is_active": False,
        "requires_zones": False,
    }
    defaults.update(overrides)
    return Treatment.objects.create(**defaults)


def _make_combo(category: Category, **overrides) -> Combo:
    defaults = {
        "slug": _uid("combo-slug"),
        "title": _uid("Combo"),
        "category": category,
        "price": 120,
        "is_active": False,
        "sessions": 0,
    }
    defaults.update(overrides)
    return Combo.objects.create(**defaults)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("existing_factory", "payload_factory", "url", "model_name"),
    [
        (_make_journey, _journey_payload, "/api/v1/catalog/journeys/", "Journey"),
        (_make_treatment, _treatment_payload, "/api/v1/catalog/treatments/", "Treatment"),
        (_make_combo, _combo_payload, "/api/v1/catalog/combos/", "Combo"),
    ],
)
def test_api_same_category_duplicate_slug_rejects(
    existing_factory, payload_factory, url, model_name
):
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    existing_factory(category, slug="shared-slug")

    resp = client.post(url, payload_factory(category, slug="shared-slug"), format="json")

    assert resp.status_code == 400
    assert resp.data["slug"] == [
        f"Ya existe {model_name} con este Slug en esta categoría."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("existing_factory", "payload_factory", "url", "model_name"),
    [
        (_make_journey, _journey_payload, "/api/v1/catalog/journeys/", "Journey"),
        (_make_treatment, _treatment_payload, "/api/v1/catalog/treatments/", "Treatment"),
        (_make_combo, _combo_payload, "/api/v1/catalog/combos/", "Combo"),
    ],
)
def test_api_same_category_duplicate_title_rejects(
    existing_factory, payload_factory, url, model_name
):
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    existing_factory(category, title="Shared Title")

    resp = client.post(url, payload_factory(category, title="Shared Title"), format="json")

    assert resp.status_code == 400
    assert resp.data["title"] == [
        f"Ya existe {model_name} con este Title en esta categoría."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("existing_factory", "payload_factory", "url"),
    [
        (_make_journey, _journey_payload, "/api/v1/catalog/journeys/"),
        (_make_treatment, _treatment_payload, "/api/v1/catalog/treatments/"),
        (_make_combo, _combo_payload, "/api/v1/catalog/combos/"),
    ],
)
def test_api_same_slug_and_title_in_different_category_allows(
    existing_factory, payload_factory, url
):
    client = APIClient()
    client.force_authenticate(_make_staff())
    category_a = _make_category()
    category_b = _make_category()
    existing_factory(category_a, slug="shared-slug", title="Shared Title")

    resp = client.post(
        url,
        payload_factory(category_b, slug="shared-slug", title="Shared Title"),
        format="json",
    )

    assert resp.status_code in (200, 201)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("existing_factory", "payload_factory", "url", "model_name", "field_name", "shared_value"),
    [
        (_make_combo, _treatment_payload, "/api/v1/catalog/treatments/", "Combo", "slug", "shared-slug"),
        (_make_combo, _treatment_payload, "/api/v1/catalog/treatments/", "Combo", "title", "Shared Title"),
        (_make_treatment, _combo_payload, "/api/v1/catalog/combos/", "Treatment", "slug", "shared-slug"),
        (_make_treatment, _combo_payload, "/api/v1/catalog/combos/", "Treatment", "title", "Shared Title"),
    ],
)
def test_api_cross_model_same_category_rejects(
    existing_factory,
    payload_factory,
    url,
    model_name,
    field_name,
    shared_value,
):
    client = APIClient()
    client.force_authenticate(_make_staff())
    category = _make_category()
    existing_factory(category, **{field_name: shared_value})

    resp = client.post(
        url,
        payload_factory(category, **{field_name: shared_value}),
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data[field_name] == [
        f"Ya existe {model_name} con este {field_name.title()} en esta categoría."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("existing_factory", "payload_factory", "url"),
    [
        (_make_combo, _treatment_payload, "/api/v1/catalog/treatments/"),
        (_make_treatment, _combo_payload, "/api/v1/catalog/combos/"),
    ],
)
def test_api_cross_model_different_category_allows(existing_factory, payload_factory, url):
    client = APIClient()
    client.force_authenticate(_make_staff())
    category_a = _make_category()
    category_b = _make_category()
    existing_factory(category_a, slug="shared-slug", title="Shared Title")

    resp = client.post(
        url,
        payload_factory(category_b, slug="shared-slug", title="Shared Title"),
        format="json",
    )

    assert resp.status_code in (200, 201)


@pytest.mark.django_db
def test_journey_serializer_allows_partial_update_without_changing_slug_or_title():
    category = _make_category()
    journey = _make_journey(category)

    serializer = JourneySerializer(
        instance=journey,
        data={"short_description": "Actualizado"},
        partial=True,
    )

    assert serializer.is_valid() is True


@pytest.mark.django_db
def test_journey_serializer_rejects_category_change_when_slug_conflicts():
    category_a = _make_category()
    category_b = _make_category()
    journey = _make_journey(category_a, slug="shared-slug")
    _make_journey(category_b, slug="shared-slug")

    serializer = JourneySerializer(
        instance=journey,
        data={"category": str(category_b.id)},
        partial=True,
    )

    assert serializer.is_valid() is False
    assert serializer.errors["slug"] == [
        "Ya existe Journey con este Slug en esta categoría."
    ]


@pytest.mark.django_db
def test_journey_serializer_rejects_category_change_when_title_conflicts():
    category_a = _make_category()
    category_b = _make_category()
    journey = _make_journey(category_a, title="Shared Title")
    _make_journey(category_b, title="Shared Title")

    serializer = JourneySerializer(
        instance=journey,
        data={"category": str(category_b.id)},
        partial=True,
    )

    assert serializer.is_valid() is False
    assert serializer.errors["title"] == [
        "Ya existe Journey con este Title en esta categoría."
    ]


@pytest.mark.django_db
def test_api_treatment_by_slug_ambiguous_returns_400():
    client = APIClient()
    category_a = _make_category()
    category_b = _make_category()
    _make_treatment(category_a, slug="shared-slug", is_active=True)
    _make_treatment(category_b, slug="shared-slug", is_active=True)

    resp = client.get("/api/v1/catalog/treatments/by-slug/shared-slug/")

    assert resp.status_code == 400
    assert resp.data["slug"] == [
        "Hay más de un resultado para este slug. Envíe category o category_id."
    ]


@pytest.mark.django_db
def test_api_treatment_by_slug_with_category_disambiguates():
    client = APIClient()
    category_a = _make_category()
    category_b = _make_category()
    treatment_a = _make_treatment(category_a, slug="shared-slug", is_active=True)
    _make_treatment(category_b, slug="shared-slug", is_active=True)

    resp = client.get(
        f"/api/v1/catalog/treatments/by-slug/shared-slug/?category={category_a.slug}"
    )

    assert resp.status_code == 200
    assert resp.data["id"] == str(treatment_a.id)


@pytest.mark.django_db
def test_api_treatment_by_slug_with_category_id_disambiguates():
    client = APIClient()
    category_a = _make_category()
    category_b = _make_category()
    _make_treatment(category_a, slug="shared-slug", is_active=True)
    treatment_b = _make_treatment(category_b, slug="shared-slug", is_active=True)

    resp = client.get(
        f"/api/v1/catalog/treatments/by-slug/shared-slug/?category_id={category_b.id}"
    )

    assert resp.status_code == 200
    assert resp.data["id"] == str(treatment_b.id)

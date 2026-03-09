import pytest
from rest_framework.test import APIClient

from apps.reviews.models import ManualReview
from apps.reviews import services


def _disable_throttling(settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_CLASSES": [],
    }


@pytest.mark.django_db
def test_reviews_endpoint_manual_filters_defaults(settings):
    _disable_throttling(settings)
    settings.REVIEWS_PROVIDER = "manual"
    settings.REVIEWS_DEFAULT_MIN_RATING = 4
    settings.REVIEWS_DEFAULT_WITH_CONTENT = True
    settings.REVIEWS_PUBLIC_LIMIT = 10

    ManualReview.objects.create(
        author_name="Review 5",
        rating=5,
        comment="Excelente servicio",
        is_active=True,
        order=0,
    )
    ManualReview.objects.create(
        author_name="Review 4 vacia",
        rating=4,
        comment="",
        is_active=True,
        order=1,
    )
    ManualReview.objects.create(
        author_name="Review 3",
        rating=3,
        comment="No entra por rating",
        is_active=True,
        order=2,
    )
    ManualReview.objects.create(
        author_name="Review inactiva",
        rating=5,
        comment="No entra por estado",
        is_active=False,
        order=3,
    )

    client = APIClient()
    response = client.get("/api/v1/reviews/?with_content=true&min_rating=4")

    assert response.status_code == 200
    assert response.data["requested_provider"] == "manual"
    assert response.data["provider"] == "manual"
    assert response.data["count"] == 1
    assert response.data["items"][0]["author_name"] == "Review 5"


@pytest.mark.django_db
def test_reviews_endpoint_query_allows_empty_comment(settings):
    _disable_throttling(settings)
    settings.REVIEWS_PROVIDER = "manual"

    ManualReview.objects.create(
        author_name="Review con texto",
        rating=5,
        comment="Excelente",
        is_active=True,
        order=0,
    )
    ManualReview.objects.create(
        author_name="Review sin texto",
        rating=4,
        comment="",
        is_active=True,
        order=1,
    )

    client = APIClient()
    response = client.get("/api/v1/reviews/?with_content=false&min_rating=4")

    assert response.status_code == 200
    assert response.data["provider"] == "manual"
    assert response.data["count"] == 2


@pytest.mark.django_db
def test_reviews_endpoint_google_fallbacks_to_manual(settings):
    _disable_throttling(settings)
    settings.REVIEWS_PROVIDER = "google"
    settings.REVIEWS_FALLBACK_TO_MANUAL = True
    settings.REVIEWS_GOOGLE_AUTO_SYNC_ON_READ = True
    settings.REVIEWS_GOOGLE_ACCOUNT_ID = ""
    settings.REVIEWS_GOOGLE_LOCATION_ID = ""
    settings.REVIEWS_PUBLIC_LIMIT = 10

    ManualReview.objects.create(
        author_name="Fallback review",
        rating=5,
        comment="Manual para fallback",
        is_active=True,
        order=0,
    )

    client = APIClient()
    response = client.get("/api/v1/reviews/")

    assert response.status_code == 200
    assert response.data["requested_provider"] == "google"
    assert response.data["provider"] == "manual"
    assert response.data["fallback_reason"] is not None
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_reviews_endpoint_google_no_sync_on_read_when_disabled(settings, monkeypatch):
    _disable_throttling(settings)
    settings.REVIEWS_PROVIDER = "google"
    settings.REVIEWS_GOOGLE_AUTO_SYNC_ON_READ = False

    sync_called = False

    def _fake_sync():
        nonlocal sync_called
        sync_called = True
        return {"received": 0, "synced": 0}

    monkeypatch.setattr(services, "sync_google_reviews", _fake_sync)

    client = APIClient()
    response = client.get("/api/v1/reviews/")

    assert response.status_code == 200
    assert response.data["provider"] == "google"
    assert response.data["count"] == 0
    assert sync_called is False

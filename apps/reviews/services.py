from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import GoogleReviewCache, ManualReview

GOOGLE_REVIEWS_PAGE_SIZE = 50
GOOGLE_STAR_RATING_MAP = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
}


class GoogleReviewsError(Exception):
    pass


@dataclass
class PublicReviewsResult:
    requested_provider: str
    provider: str
    fallback_reason: str | None
    items: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested_provider": self.requested_provider,
            "provider": self.provider,
            "fallback_reason": self.fallback_reason,
            "count": len(self.items),
            "items": self.items,
            "generated_at": timezone.now().isoformat(),
        }


def get_public_reviews(
    *,
    provider: str,
    min_rating: int,
    with_content: bool,
    limit: int,
) -> dict[str, Any]:
    if provider == "google":
        try:
            _ensure_google_cache()
            items = _load_google_reviews(
                min_rating=min_rating,
                with_content=with_content,
                limit=limit,
            )
            return PublicReviewsResult(
                requested_provider="google",
                provider="google",
                fallback_reason=None,
                items=items,
            ).as_dict()
        except GoogleReviewsError as exc:
            if not settings.REVIEWS_FALLBACK_TO_MANUAL:
                raise
            items = _load_manual_reviews(
                min_rating=min_rating,
                with_content=with_content,
                limit=limit,
            )
            return PublicReviewsResult(
                requested_provider="google",
                provider="manual",
                fallback_reason=str(exc),
                items=items,
            ).as_dict()

    items = _load_manual_reviews(
        min_rating=min_rating,
        with_content=with_content,
        limit=limit,
    )
    return PublicReviewsResult(
        requested_provider="manual",
        provider="manual",
        fallback_reason=None,
        items=items,
    ).as_dict()


def sync_google_reviews() -> dict[str, int]:
    raw_reviews = _fetch_google_reviews()
    fetched_at = timezone.now()
    synced = 0

    with transaction.atomic():
        for raw_review in raw_reviews:
            normalized = _normalize_google_review(raw_review, fetched_at=fetched_at)
            external_id = normalized.pop("external_id", "")
            if not external_id:
                continue

            obj, created = GoogleReviewCache.objects.get_or_create(
                external_id=external_id,
                defaults=normalized,
            )
            if not created:
                for key, value in normalized.items():
                    setattr(obj, key, value)
                obj.save()
            synced += 1

        _purge_old_google_cache()

    return {"received": len(raw_reviews), "synced": synced}


def _ensure_google_cache() -> None:
    if not settings.REVIEWS_GOOGLE_AUTO_SYNC_ON_READ:
        return

    if not GoogleReviewCache.objects.exists():
        sync_google_reviews()
        return

    latest_fetch = GoogleReviewCache.objects.order_by("-fetched_at").values_list(
        "fetched_at", flat=True
    ).first()
    if latest_fetch is None:
        sync_google_reviews()
        return

    refresh_cutoff = timezone.now() - timedelta(
        hours=settings.REVIEWS_CACHE_REFRESH_HOURS
    )
    if latest_fetch < refresh_cutoff:
        sync_google_reviews()


def _load_manual_reviews(
    *,
    min_rating: int,
    with_content: bool,
    limit: int,
) -> list[dict[str, Any]]:
    queryset = (
        ManualReview.objects.filter(is_active=True, rating__gte=min_rating)
        .order_by("order", "-created_at")[:limit]
    )
    reviews = []
    for review in queryset:
        if with_content and not (review.comment or "").strip():
            continue
        reviews.append(
            {
                "id": str(review.id),
                "source": "manual",
                "author_name": review.author_name,
                "rating": review.rating,
                "comment": review.comment,
                "profile_photo_url": "",
                "published_at": review.created_at.isoformat(),
            }
        )
    return reviews


def _load_google_reviews(
    *,
    min_rating: int,
    with_content: bool,
    limit: int,
) -> list[dict[str, Any]]:
    queryset = GoogleReviewCache.objects.filter(is_hidden=False, rating__gte=min_rating)
    queryset = queryset.order_by("-update_time", "-create_time", "-fetched_at")[:limit]

    reviews = []
    for review in queryset:
        if with_content and not (review.comment or "").strip():
            continue
        published_at = review.update_time or review.create_time or review.fetched_at
        reviews.append(
            {
                "id": review.external_id,
                "source": "google",
                "author_name": review.reviewer_name or "Anonimo",
                "rating": review.rating,
                "comment": review.comment,
                "profile_photo_url": review.reviewer_profile_photo_url,
                "published_at": published_at.isoformat(),
            }
        )
    return reviews


def _fetch_google_reviews() -> list[dict[str, Any]]:
    account_id = settings.REVIEWS_GOOGLE_ACCOUNT_ID
    location_id = settings.REVIEWS_GOOGLE_LOCATION_ID
    if not account_id or not location_id:
        raise GoogleReviewsError(
            "Falta REVIEWS_GOOGLE_ACCOUNT_ID o REVIEWS_GOOGLE_LOCATION_ID."
        )

    base_url = (
        f"https://mybusiness.googleapis.com/v4/accounts/{account_id}"
        f"/locations/{location_id}/reviews"
    )
    headers = {
        "Authorization": f"Bearer {_get_google_access_token()}",
        "Accept": "application/json",
    }
    params: dict[str, Any] = {
        "pageSize": GOOGLE_REVIEWS_PAGE_SIZE,
        "orderBy": "updateTime desc",
    }
    reviews: list[dict[str, Any]] = []

    while True:
        response = requests.get(base_url, headers=headers, params=params, timeout=20)
        if response.status_code >= 400:
            raise GoogleReviewsError(
                f"Google Reviews API error ({response.status_code}): {response.text}"
            )
        payload = response.json()
        reviews.extend(payload.get("reviews", []))
        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break
        params["pageToken"] = next_page_token

    return reviews


def _get_google_access_token() -> str:
    static_access_token = settings.REVIEWS_GOOGLE_ACCESS_TOKEN
    if static_access_token:
        return static_access_token

    refresh_token = settings.REVIEWS_GOOGLE_REFRESH_TOKEN
    client_id = settings.REVIEWS_GOOGLE_CLIENT_ID
    client_secret = settings.REVIEWS_GOOGLE_CLIENT_SECRET
    if not (refresh_token and client_id and client_secret):
        raise GoogleReviewsError(
            "Faltan credenciales de Google OAuth para obtener access token."
        )

    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise GoogleReviewsError(
            f"OAuth token error ({response.status_code}): {response.text}"
        )

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise GoogleReviewsError("Google OAuth no devolvio access_token.")
    return access_token


def _normalize_google_review(
    raw_review: dict[str, Any], *, fetched_at
) -> dict[str, Any]:
    reviewer = raw_review.get("reviewer", {}) or {}
    rating = _parse_rating(raw_review.get("starRating"))
    if rating <= 0:
        rating = _parse_rating(raw_review.get("rating"))
    if rating <= 0:
        rating = 5

    return {
        "external_id": str(raw_review.get("reviewId") or raw_review.get("name") or ""),
        "reviewer_name": (reviewer.get("displayName") or "").strip(),
        "reviewer_profile_photo_url": reviewer.get("profilePhotoUrl", ""),
        "reviewer_is_anonymous": bool(reviewer.get("isAnonymous", False)),
        "rating": rating,
        "comment": raw_review.get("comment", "") or "",
        "create_time": _parse_google_datetime(raw_review.get("createTime")),
        "update_time": _parse_google_datetime(raw_review.get("updateTime")),
        "fetched_at": fetched_at,
        "raw_payload": raw_review,
    }


def _parse_rating(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in GOOGLE_STAR_RATING_MAP:
            return GOOGLE_STAR_RATING_MAP[normalized]
        if normalized.isdigit():
            return int(normalized)
    return 0


def _parse_google_datetime(value: Any):
    if not value or not isinstance(value, str):
        return None
    return parse_datetime(value)


def _purge_old_google_cache() -> int:
    keep_days = max(int(settings.REVIEWS_CACHE_DAYS), 1)
    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted, _ = GoogleReviewCache.objects.filter(fetched_at__lt=cutoff).delete()
    return deleted

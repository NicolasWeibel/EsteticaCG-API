import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.authcodes.models import OTPLoginCode


def _disable_throttling(settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_CLASSES": [],
    }


@pytest.mark.django_db
def test_verify_code_sets_http_only_cookies_and_me_uses_them(settings):
    _disable_throttling(settings)
    email = "cookie-login@example.com"
    _, raw_code = OTPLoginCode.create_fresh(email=email)

    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        "/api/v1/auth/verify-code/",
        {"email": email, "code": raw_code},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["csrfToken"]
    assert "access" not in response.data
    assert "refresh" not in response.data
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    assert response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME]["httponly"]
    assert (
        response.cookies[settings.AUTH_COOKIE_ACCESS_NAME]["samesite"]
        == settings.AUTH_COOKIE_SAMESITE
    )

    me_response = client.get("/api/v1/auth/me/")

    assert me_response.status_code == 200
    assert me_response.data["email"] == email


@pytest.mark.django_db
def test_refresh_reads_refresh_cookie_and_rotates_auth_cookies(settings):
    _disable_throttling(settings)
    email = "refresh-cookie@example.com"
    _, raw_code = OTPLoginCode.create_fresh(email=email)

    client = APIClient(enforce_csrf_checks=True)
    login_response = client.post(
        "/api/v1/auth/verify-code/",
        {"email": email, "code": raw_code},
        format="json",
    )
    old_access = login_response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    old_refresh = login_response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value
    csrf_token = login_response.data["csrfToken"]

    refresh_response = client.post(
        "/api/v1/auth/jwt/refresh/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert refresh_response.status_code == 200
    assert refresh_response.data["success"] is True
    assert (
        refresh_response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value != old_access
    )
    assert (
        refresh_response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value != old_refresh
    )
    assert refresh_response.data["csrfToken"]


@pytest.mark.django_db
def test_logout_clears_auth_cookies(settings):
    _disable_throttling(settings)
    email = "logout-cookie@example.com"
    _, raw_code = OTPLoginCode.create_fresh(email=email)

    client = APIClient(enforce_csrf_checks=True)
    login_response = client.post(
        "/api/v1/auth/verify-code/",
        {"email": email, "code": raw_code},
        format="json",
    )
    csrf_token = login_response.data["csrfToken"]

    logout_response = client.post(
        "/api/v1/auth/logout/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert logout_response.status_code == 204
    assert logout_response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value == ""
    assert logout_response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value == ""

    me_response = client.get("/api/v1/auth/me/")

    assert me_response.status_code == 401


@pytest.mark.django_db
def test_google_callback_sets_cookies_and_redirects_without_tokens_in_url(settings):
    _disable_throttling(settings)
    settings.ACCOUNT_ALLOWED_REDIRECT_URLS = ["http://localhost:5173/mi-cuenta"]
    settings.ACCOUNT_ALLOWED_REDIRECT_URL_REGEXES = []

    user = get_user_model().objects.create_user(email="google-cookie@example.com")
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)

    response = client.get(
        "/api/v1/auth/google/callback/?next=http://localhost:5173/mi-cuenta"
    )

    assert response.status_code == 302
    assert response.url == "http://localhost:5173/mi-cuenta?oauth_success=true"
    assert "access=" not in response.url
    assert "refresh=" not in response.url
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    assert response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value


@pytest.mark.django_db
def test_session_to_jwt_sets_cookies_instead_of_returning_tokens(settings):
    _disable_throttling(settings)
    user = get_user_model().objects.create_user(email="session-cookie@example.com")
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    csrf_response = client.get("/api/v1/auth/csrf/")

    response = client.post(
        "/api/v1/auth/session-to-jwt/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_response.data["csrfToken"],
    )

    assert response.status_code == 200
    assert response.data["success"] is True
    assert response.data["csrfToken"]
    assert response.data["user"]["email"] == user.email
    assert "access" not in response.data
    assert "refresh" not in response.data
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    assert response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value


@pytest.mark.django_db
def test_csrf_endpoint_returns_token_for_cross_site_frontends(settings):
    _disable_throttling(settings)
    client = APIClient(enforce_csrf_checks=True)

    response = client.get("/api/v1/auth/csrf/")

    assert response.status_code == 200
    assert response.data["csrfToken"]


@pytest.mark.django_db
def test_refresh_rejects_missing_csrf_header(settings):
    _disable_throttling(settings)
    email = "csrf-refresh@example.com"
    _, raw_code = OTPLoginCode.create_fresh(email=email)

    client = APIClient(enforce_csrf_checks=True)
    client.post(
        "/api/v1/auth/verify-code/",
        {"email": email, "code": raw_code},
        format="json",
    )

    response = client.post("/api/v1/auth/jwt/refresh/", {}, format="json")

    assert response.status_code == 403
    assert "CSRF Failed" in response.data["detail"]


@pytest.mark.django_db
def test_cookie_authenticated_write_requires_csrf(settings):
    _disable_throttling(settings)
    email = "csrf-protected@example.com"
    _, raw_code = OTPLoginCode.create_fresh(email=email)

    client = APIClient(enforce_csrf_checks=True)
    login_response = client.post(
        "/api/v1/auth/verify-code/",
        {"email": email, "code": raw_code},
        format="json",
    )

    forbidden = client.put("/api/v1/auth/me/", {}, format="json")

    assert forbidden.status_code == 403
    assert "CSRF Failed" in forbidden.data["detail"]

    allowed = client.put(
        "/api/v1/auth/me/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=login_response.data["csrfToken"],
    )

    assert allowed.status_code == 200
    assert allowed.data["email"] == email

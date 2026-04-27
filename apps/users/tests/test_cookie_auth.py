import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.authcodes.models import OTPLoginCode
from apps.users.models import Client


def _disable_throttling(settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_CLASSES": [],
    }


def _cloudinary_id(path: str) -> str:
    prefix = django_settings.CLOUDINARY_STORAGE.get("PREFIX", "")
    return f"{prefix}/{path}" if prefix else path


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
def test_refresh_rejects_reused_blacklisted_refresh_token(settings):
    _disable_throttling(settings)
    email = "blacklisted-refresh@example.com"
    _, raw_code = OTPLoginCode.create_fresh(email=email)

    client = APIClient(enforce_csrf_checks=True)
    login_response = client.post(
        "/api/v1/auth/verify-code/",
        {"email": email, "code": raw_code},
        format="json",
    )
    original_refresh = login_response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value

    refresh_response = client.post(
        "/api/v1/auth/jwt/refresh/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=login_response.data["csrfToken"],
    )

    assert refresh_response.status_code == 200

    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = original_refresh
    reused_refresh_response = client.post(
        "/api/v1/auth/jwt/refresh/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=refresh_response.data["csrfToken"],
    )

    assert reused_refresh_response.status_code == 401
    assert reused_refresh_response.data["code"] == "token_not_valid"
    assert "blacklisted" in reused_refresh_response.data["detail"].lower()
    assert reused_refresh_response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value == ""
    assert reused_refresh_response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value == ""


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


@pytest.mark.django_db
def test_me_rejects_multipart_with_global_json_parser():
    user = get_user_model().objects.create_user(email="multipart-me@example.com")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.put(
        "/api/v1/auth/me/",
        {},
        format="multipart",
    )

    assert response.status_code == 415


@pytest.mark.django_db
def test_client_avatar_upload_signature_requires_auth():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/upload/client-avatar/sign/",
        {"filename": "avatar.png"},
        format="json",
    )

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_client_avatar_upload_signature_returns_cloudinary_avatar_prefix():
    user = get_user_model().objects.create_user(email="multipart-profile@example.com")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/v1/auth/upload/client-avatar/sign/",
        {"filename": "avatar.png"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["resource_type"] == "image"
    assert response.data["final_public_id"].startswith(
        f"{_cloudinary_id('users/clients/avatars')}/"
    )


@pytest.mark.django_db
def test_profile_accepts_custom_avatar_ref_json_and_clear():
    user = get_user_model().objects.create_user(email="multipart-profile@example.com")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        "/api/v1/auth/profile/",
        {
            "first_name": "Nico",
            "custom_avatar_ref": {
                "public_id": _cloudinary_id("users/clients/avatars/profile-avatar")
            },
        },
        format="json",
    )

    assert response.status_code == 200
    managed_client = Client.objects.get(user=user)
    assert managed_client.first_name == "Nico"
    assert managed_client.custom_avatar.name == _cloudinary_id(
        "users/clients/avatars/profile-avatar"
    )

    response = client.patch(
        "/api/v1/auth/profile/",
        {
            "custom_avatar_ref": None,
        },
        format="json",
    )

    assert response.status_code == 200
    managed_client.refresh_from_db()
    assert not managed_client.custom_avatar


@pytest.mark.django_db
def test_profile_rejects_multipart_for_custom_avatar():
    user = get_user_model().objects.create_user(email="multipart-profile@example.com")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        "/api/v1/auth/profile/",
        {
            "first_name": "Nico",
        },
        format="multipart",
    )

    assert response.status_code == 415


@pytest.mark.django_db
def test_client_admin_accepts_custom_avatar_ref_json():
    admin = get_user_model().objects.create_superuser(
        email="admin-clients@example.com",
        password="admin1234",
    )
    managed_user = get_user_model().objects.create_user(email="managed@example.com")
    managed_client = Client.objects.create(
        user=managed_user,
        email=managed_user.email,
        first_name="Before",
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.patch(
        f"/api/v1/auth/clients/{managed_client.id}/",
        {
            "first_name": "After",
            "custom_avatar_ref": {
                "public_id": _cloudinary_id("users/clients/avatars/admin-avatar")
            },
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["first_name"] == "After"
    managed_client.refresh_from_db()
    assert managed_client.custom_avatar.name == _cloudinary_id(
        "users/clients/avatars/admin-avatar"
    )


@pytest.mark.django_db
def test_client_admin_rejects_multipart_for_avatar():
    admin = get_user_model().objects.create_superuser(
        email="admin-clients@example.com",
        password="admin1234",
    )
    managed_user = get_user_model().objects.create_user(email="managed@example.com")
    managed_client = Client.objects.create(
        user=managed_user,
        email=managed_user.email,
        first_name="Before",
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.patch(
        f"/api/v1/auth/clients/{managed_client.id}/",
        {
            "first_name": "After",
        },
        format="multipart",
    )

    assert response.status_code == 415

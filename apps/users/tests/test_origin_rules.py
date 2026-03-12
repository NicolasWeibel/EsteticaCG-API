from django.test import RequestFactory, override_settings

from apps.users.api.v1.views import _is_allowed_next
from core.middleware import LanAwareCsrfViewMiddleware


@override_settings(
    ACCOUNT_ALLOWED_REDIRECT_URLS=["http://localhost:5173/mi-cuenta"],
    ACCOUNT_ALLOWED_REDIRECT_URL_REGEXES=[],
)
def test_allowed_next_accepts_exact_match():
    assert _is_allowed_next("http://localhost:5173/mi-cuenta")


@override_settings(
    ACCOUNT_ALLOWED_REDIRECT_URLS=[],
    ACCOUNT_ALLOWED_REDIRECT_URL_REGEXES=[
        r"^http://192\.168\.1\.\d{1,3}:5173/(mi-cuenta|auth/callback)/?$"
    ],
)
def test_allowed_next_accepts_lan_regex():
    assert _is_allowed_next("http://192.168.1.44:5173/auth/callback")


@override_settings(
    ACCOUNT_ALLOWED_REDIRECT_URLS=[],
    ACCOUNT_ALLOWED_REDIRECT_URL_REGEXES=[
        r"^http://192\.168\.1\.\d{1,3}:5173/(mi-cuenta|auth/callback)/?$"
    ],
)
def test_allowed_next_rejects_other_paths_or_subnets():
    assert not _is_allowed_next("http://192.168.2.44:5173/auth/callback")
    assert not _is_allowed_next("http://192.168.1.44:5173/admin")


@override_settings(
    CSRF_TRUSTED_ORIGINS=[],
    CSRF_TRUSTED_ORIGIN_REGEXES=[r"^http://192\.168\.1\.\d{1,3}:5173$"],
)
def test_csrf_middleware_accepts_lan_origin_regex():
    middleware = LanAwareCsrfViewMiddleware(lambda request: None)
    request = RequestFactory().post(
        "/api/v1/auth/session-to-jwt/",
        HTTP_ORIGIN="http://192.168.1.44:5173",
    )
    assert middleware._origin_verified(request) is True


@override_settings(
    CSRF_TRUSTED_ORIGINS=[],
    CSRF_TRUSTED_ORIGIN_REGEXES=[r"^http://192\.168\.1\.\d{1,3}:5173$"],
)
def test_csrf_middleware_rejects_other_subnet():
    middleware = LanAwareCsrfViewMiddleware(lambda request: None)
    request = RequestFactory().post(
        "/api/v1/auth/session-to-jwt/",
        HTTP_ORIGIN="http://192.168.2.44:5173",
    )
    assert middleware._origin_verified(request) is False

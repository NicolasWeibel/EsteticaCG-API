from django.conf import settings

from core.csrf import issue_csrf_token


def _cookie_domain():
    return getattr(settings, "AUTH_COOKIE_DOMAIN", None) or None


def _cookie_kwargs(max_age: int) -> dict:
    return {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": settings.AUTH_COOKIE_PATH,
        "domain": _cookie_domain(),
        "max_age": max_age,
    }


def get_access_cookie_max_age() -> int:
    return int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())


def get_refresh_cookie_max_age() -> int:
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_access_cookie(response, token: str):
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS_NAME,
        token,
        **_cookie_kwargs(get_access_cookie_max_age()),
    )
    return response


def set_refresh_cookie(response, token: str):
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        token,
        **_cookie_kwargs(get_refresh_cookie_max_age()),
    )
    return response


def set_auth_cookies(response, *, access_token: str, refresh_token: str | None = None):
    set_access_cookie(response, access_token)
    if refresh_token is not None:
        set_refresh_cookie(response, refresh_token)
    return response


def clear_auth_cookies(response):
    delete_kwargs = {
        "path": settings.AUTH_COOKIE_PATH,
        "domain": _cookie_domain(),
        "samesite": settings.AUTH_COOKIE_SAMESITE,
    }
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS_NAME, **delete_kwargs)
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH_NAME, **delete_kwargs)
    return response


def attach_csrf_token(request, response) -> str:
    token = issue_csrf_token(request)
    if hasattr(response, "data") and isinstance(response.data, dict):
        response.data["csrfToken"] = token
    return token

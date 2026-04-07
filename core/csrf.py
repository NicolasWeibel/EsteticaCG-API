from django.core.exceptions import ImproperlyConfigured
from django.middleware.csrf import get_token
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck


def validate_cookie_settings(samesite_value: str, secure_value: bool):
    samesite = str(samesite_value).strip().lower()
    if samesite not in {"lax", "strict", "none"}:
        raise ImproperlyConfigured(
            "AUTH_COOKIE_SAMESITE must be one of: Lax, Strict, None."
        )
    if samesite == "none" and not secure_value:
        raise ImproperlyConfigured(
            "AUTH_COOKIE_SECURE must be True when AUTH_COOKIE_SAMESITE=None."
        )


def issue_csrf_token(request) -> str:
    return get_token(request)


def enforce_csrf(request):
    check = CSRFCheck(lambda _request: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")

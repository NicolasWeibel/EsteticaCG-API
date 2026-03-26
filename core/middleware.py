import re
import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.functional import cached_property


class HealthzShortCircuitMiddleware:
    """Return 200 for /healthz without running the rest of the middleware chain."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in {"GET", "HEAD"} and request.path_info in {
            "/healthz",
            "/healthz/",
        }:
            response = HttpResponse(status=200)
            response["Cache-Control"] = "no-store"
            return response
        return self.get_response(request)


class ProxySecretMiddleware:
    """Optionally require a shared secret for requests that must come via a proxy."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "REQUIRE_PROXY_SECRET", False):
            return self.get_response(request)

        path = request.path_info or "/"
        exempt_prefixes = getattr(settings, "PROXY_SECRET_EXEMPT_PATH_PREFIXES", [])
        if any(path.startswith(prefix) for prefix in exempt_prefixes):
            return self.get_response(request)

        expected = getattr(settings, "PROXY_SHARED_SECRET", "")
        received = request.headers.get("X-Proxy-Secret", "")

        if expected and secrets.compare_digest(received, expected):
            return self.get_response(request)

        return JsonResponse({"detail": "Forbidden."}, status=403)


class LanAwareCsrfViewMiddleware(CsrfViewMiddleware):
    """Allow regex-based CSRF origins for local LAN frontends."""

    @cached_property
    def allowed_origin_regexes(self):
        return [
            re.compile(pattern)
            for pattern in getattr(settings, "CSRF_TRUSTED_ORIGIN_REGEXES", [])
            if pattern
        ]

    def _origin_verified(self, request):
        if super()._origin_verified(request):
            return True

        request_origin = request.META.get("HTTP_ORIGIN")
        if not request_origin:
            return False

        return any(
            pattern.fullmatch(request_origin) for pattern in self.allowed_origin_regexes
        )

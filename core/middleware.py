import re

from django.conf import settings
from django.http import HttpResponse
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

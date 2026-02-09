from django.http import HttpResponse


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

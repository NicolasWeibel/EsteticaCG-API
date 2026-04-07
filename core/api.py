from rest_framework.views import APIView

from core.csrf import enforce_csrf


class CookieCsrfProtectedAPIView(APIView):
    csrf_cookie_names = ()

    def should_enforce_csrf(self, request) -> bool:
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return False
        return any(request.COOKIES.get(name) for name in self.csrf_cookie_names)

    def initial(self, request, *args, **kwargs):
        if self.should_enforce_csrf(request):
            enforce_csrf(request)
        super().initial(request, *args, **kwargs)

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.csrf import enforce_csrf


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = None
        used_cookie = False

        if header is not None:
            raw_token = self.get_raw_token(header)

        if raw_token is None:
            cookie_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
            if not cookie_token:
                return None
            raw_token = cookie_token.encode("utf-8")
            used_cookie = True

        validated_token = self.get_validated_token(raw_token)
        if used_cookie and request.method not in {"GET", "HEAD", "OPTIONS"}:
            enforce_csrf(request)
        return self.get_user(validated_token), validated_token

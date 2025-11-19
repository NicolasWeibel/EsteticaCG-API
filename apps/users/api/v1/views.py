# ===========================================
# apps/users/api/v1/views.py
# ===========================================
from urllib.parse import urlencode, urlparse
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserMeSerializer


def _is_allowed_next(next_url: str) -> bool:
    if not next_url:
        return False
    # compara esquema+host+path con whitelist exacta
    parsed = urlparse(next_url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return normalized in set(settings.ACCOUNT_ALLOWED_REDIRECT_URLS)


def _safe_next(next_url: str | None) -> str:
    if next_url and _is_allowed_next(next_url):
        return next_url
    return settings.FRONTEND_LOGIN_REDIRECT_URL


class GoogleLoginStartView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        final_next = _safe_next(request.GET.get("next"))
        # tras Google, allauth redirige a nuestro "complete" con el next del frontend
        complete_url = request.build_absolute_uri(
            reverse("users_api_v1:google-complete")
        )
        qs_complete = urlencode({"next": final_next})
        redirect_after_google = f"{complete_url}?{qs_complete}"
        qs_login = urlencode({"process": "login", "next": redirect_after_google})
        return HttpResponseRedirect(f"/accounts/google/login/?{qs_login}")


class GoogleLoginCompleteView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = [SessionAuthentication]  # valida sesión si existe

    def get(self, request):
        # si no hay sesión, vuelve a iniciar el flujo
        if not request.user.is_authenticated:
            nxt = _safe_next(request.GET.get("next"))
            qs = urlencode({"next": nxt})
            start = request.build_absolute_uri(reverse("users_api_v1:google-start"))
            return HttpResponseRedirect(f"{start}?{qs}")
        # si hay sesión, redirige al frontend (SPA luego hará session→JWT)
        return HttpResponseRedirect(_safe_next(request.GET.get("next")))


class SessionToJWTView(APIView):
    authentication_classes = [SessionAuthentication]  # requiere CSRF
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh = RefreshToken.for_user(request.user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserMeSerializer(request.user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            return Response({"detail": "Falta 'refresh'."}, status=400)
        try:
            RefreshToken(token).blacklist()
        except Exception:
            return Response({"detail": "Refresh inválido."}, status=400)
        return Response(status=204)


class MeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserMeSerializer(request.user).data)

    def put(self, request):
        ser = UserMeSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


def google_login_start(request):
    """
    Redirige desde /api/v1/auth/google/login/ al login real de allauth
    (/accounts/google/login/) pasando ?next=… y activando el flujo inmediato.
    """
    next_url = request.GET.get("next") or getattr(
        settings, "FRONTEND_LOGIN_REDIRECT_URL", "/"
    )

    # Si next es absoluto, validá contra la lista blanca
    allowed = set(getattr(settings, "ACCOUNT_ALLOWED_REDIRECT_URLS", []))
    if next_url.startswith("http"):
        if allowed and next_url not in allowed:
            next_url = getattr(settings, "FRONTEND_LOGIN_REDIRECT_URL", "/")

    # URL de allauth para Google. Con SOCIALACCOUNT_LOGIN_ON_GET=True
    # esta URL dispara el redirect a Google sin pantalla intermedia.
    allauth_login_url = reverse("google_login")  # -> /accounts/google/login/

    query = urlencode({"process": "login", "next": next_url})
    return redirect(f"{allauth_login_url}?{query}")

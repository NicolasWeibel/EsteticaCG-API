# ===========================================
# apps/users/api/v1/views.py
# ===========================================
import re
from urllib.parse import urlencode, urlparse
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, viewsets, filters
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import (
    UserMeSerializer,
    ClientMeSerializer,
    ClientProfileUpdateSerializer,
    ClientAdminSerializer,
)
from apps.users.models import Client
from apps.users.services import update_client_profile, ClientMatchError
from apps.authcodes.models import OTPLoginCode
from apps.authcodes.tasks import send_verification_code_task


def _is_allowed_next(next_url: str) -> bool:
    if not next_url:
        return False
    # compara esquema+host+path con whitelist exacta
    parsed = urlparse(next_url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if normalized in set(settings.ACCOUNT_ALLOWED_REDIRECT_URLS):
        return True
    return any(
        re.fullmatch(pattern, normalized)
        for pattern in getattr(settings, "ACCOUNT_ALLOWED_REDIRECT_URL_REGEXES", [])
    )


def _safe_next(next_url: str | None) -> str:
    if next_url and _is_allowed_next(next_url):
        return next_url
    return settings.FRONTEND_LOGIN_REDIRECT_URL


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    name, domain = email.split("@", 1)
    if not name:
        name_mask = "***"
    elif len(name) == 1:
        name_mask = f"{name[:1]}***"
    else:
        name_mask = f"{name[:1]}***{name[-1:]}"
    if "." in domain:
        dom, rest = domain.split(".", 1)
        dom_mask = f"{dom[:1]}***" if dom else "***"
        return f"{name_mask}@{dom_mask}.{rest}"
    return f"{name_mask}@***"


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
    authentication_classes = [SessionAuthentication]

    def get(self, request):
        # 1. Si el usuario no se autenticó, volver al inicio
        if not request.user.is_authenticated:
            nxt = _safe_next(request.GET.get("next"))
            qs = urlencode({"next": nxt})
            start = request.build_absolute_uri(reverse("users_api_v1:google-start"))
            return HttpResponseRedirect(f"{start}?{qs}")

        # 2. Login exitoso: Generamos los tokens MANUALMENTE
        refresh = RefreshToken.for_user(request.user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # 3. Construimos la URL de regreso
        target_url = _safe_next(request.GET.get("next"))

        # Detectamos si usamos '?' o '&' para no romper la URL
        separator = "&" if "?" in target_url else "?"

        # 4. Redirigimos al frontend con los tokens en la URL
        final_url = (
            f"{target_url}{separator}access={access_token}&refresh={refresh_token}"
        )

        return HttpResponseRedirect(final_url)


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


class ProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        ser = ClientProfileUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            client = update_client_profile(user=request.user, data=ser.validated_data)
        except ClientMatchError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ClientMeSerializer(client).data)


class RequestDniChangeCodeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        email = request.user.email.lower().strip()
        obj, raw_code = OTPLoginCode.create_fresh(
            email=email,
            ip=request.META.get("REMOTE_ADDR"),
            purpose=OTPLoginCode.Purpose.DNI_CHANGE,
        )
        send_verification_code_task.delay(email, raw_code)
        return Response(
            {"detail": "Codigo enviado.", "sent_to": _mask_email(email)},
            status=status.HTTP_200_OK,
        )


class RequestDniClaimCodeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        dni = (request.data.get("dni") or "").strip()
        if not dni:
            return Response({"detail": "Falta 'dni'."}, status=status.HTTP_400_BAD_REQUEST)
        client = Client.objects.filter(dni=dni).first()
        if not client:
            return Response({"detail": "DNI no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if client.user_id:
            return Response(
                {"detail": "Este DNI ya esta asociado a otra cuenta."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email = client.email.lower().strip()
        obj, raw_code = OTPLoginCode.create_fresh(
            email=email,
            ip=request.META.get("REMOTE_ADDR"),
            purpose=OTPLoginCode.Purpose.DNI_CLAIM,
        )
        send_verification_code_task.delay(email, raw_code)
        return Response(
            {"detail": "Codigo enviado.", "sent_to": _mask_email(email)},
            status=status.HTTP_200_OK,
        )


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.select_related("user").all().order_by("-created_at")
    serializer_class = ClientAdminSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ("email", "dni", "first_name", "last_name", "phone_number")
    ordering_fields = (
        "created_at",
        "updated_at",
        "last_booking_date",
        "bookings_count",
        "email",
        "dni",
        "first_name",
        "last_name",
    )


def google_login_start(request):
    """
    Redirige desde /api/v1/auth/google/login/ al login real de allauth
    (/accounts/google/login/) pasando ?next=… y activando el flujo inmediato.
    """
    next_url = request.GET.get("next") or getattr(
        settings, "FRONTEND_LOGIN_REDIRECT_URL", "/"
    )

    # Si next es absoluto, validá contra la lista blanca
    if next_url.startswith("http"):
        if not _is_allowed_next(next_url):
            next_url = getattr(settings, "FRONTEND_LOGIN_REDIRECT_URL", "/")

    # URL de allauth para Google. Con SOCIALACCOUNT_LOGIN_ON_GET=True
    # esta URL dispara el redirect a Google sin pantalla intermedia.
    allauth_login_url = reverse("google_login")  # -> /accounts/google/login/

    query = urlencode({"process": "login", "next": next_url})
    return redirect(f"{allauth_login_url}?{query}")

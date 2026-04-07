# ===============================
# apps/authcodes/views.py
# ===============================
from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, throttling
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.services import ensure_client_for_user
from apps.users.api.v1.serializers import UserMeSerializer
from core.auth_cookies import attach_csrf_token, set_auth_cookies

from .serializers import RequestCodeSerializer, VerifyCodeSerializer
from .models import OTPLoginCode
from .throttles import RequestCodeThrottle
from .tasks import send_login_code_task

User = get_user_model()


class RequestCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [RequestCodeThrottle]

    def post(self, request):
        ser = RequestCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        obj, raw_code = OTPLoginCode.create_fresh(
            email=email,
            ip=request.META.get("REMOTE_ADDR"),
            purpose=OTPLoginCode.Purpose.LOGIN,
        )
        send_login_code_task.delay(email, raw_code)
        return Response({"detail": "Codigo enviado si el email es valido."})


class VerifyCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [throttling.AnonRateThrottle]

    @transaction.atomic
    def post(self, request):
        ser = VerifyCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        raw_code = ser.validated_data["code"]
        verified = OTPLoginCode.verify_latest(
            email=email, raw_code=raw_code, purpose=OTPLoginCode.Purpose.LOGIN
        )
        if not verified:
            return Response(
                {"detail": "Codigo invalido o expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, _ = User.objects.get_or_create(email=email, defaults={"is_active": True})
        ensure_client_for_user(user=user, email=email)
        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "success": True,
                "user": UserMeSerializer(user).data,
            }
        )
        response = set_auth_cookies(
            response,
            access_token=str(refresh.access_token),
            refresh_token=str(refresh),
        )
        attach_csrf_token(request, response)
        return response

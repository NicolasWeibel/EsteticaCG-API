# ===============================
# apps/authcodes/views.py
# ===============================
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, throttling
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RequestCodeSerializer, VerifyCodeSerializer
from .models import OTPLoginCode
from .throttles import RequestCodeThrottle
from .tasks import send_login_code_task

User = get_user_model()


class RequestCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RequestCodeThrottle]

    def post(self, request):
        ser = RequestCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        obj, raw_code = OTPLoginCode.create_fresh(
            email=email, ip=request.META.get("REMOTE_ADDR")
        )
        send_login_code_task.delay(email, raw_code)
        return Response({"detail": "Código enviado si el email es válido."})


class VerifyCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [throttling.AnonRateThrottle]

    @transaction.atomic
    def post(self, request):
        ser = VerifyCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower().strip()
        raw_code = ser.validated_data["code"]

        qs = (
            OTPLoginCode.objects.select_for_update()
            .filter(email=email, is_used=False, expires_at__gte=timezone.now())
            .order_by("-created_at")
        )

        if not qs.exists():
            return Response(
                {"detail": "Código inválido o expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        last_code = qs.first()
        if not last_code.verify(raw_code):
            return Response(
                {"detail": "Código inválido."}, status=status.HTTP_400_BAD_REQUEST
            )

        last_code.is_used = True
        last_code.save(update_fields=["is_used"])

        user, _ = User.objects.get_or_create(email=email, defaults={"is_active": True})
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "is_staff": getattr(user, "is_staff", False),
                },
            }
        )

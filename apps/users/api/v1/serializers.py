# apps/users/api/v1/serializers.py
from rest_framework import serializers
from apps.users.models import User, Client


class ClientMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = (
            "id",
            "email",
            "dni",
            "first_name",
            "last_name",
            "gender",
            "phone_number",
            "avatar_url",
            "birth_date",
            "created_at",
            "updated_at",
            "last_booking_date",
            "bookings_count",
        )
        read_only_fields = fields


class ClientProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    dni = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.ChoiceField(
        choices=Client.Gender.choices, required=False, allow_blank=True
    )
    phone_number = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    dni_verification_code = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )


class UserMeSerializer(serializers.ModelSerializer):
    client = ClientMeSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "is_staff", "is_superuser", "client")
        extra_kwargs = {
            "id": {"read_only": True},
            "email": {"read_only": True},
            "is_staff": {"read_only": True},
            "is_superuser": {"read_only": True},
        }

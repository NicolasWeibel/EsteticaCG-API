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


class ClientAdminSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        source="user", queryset=User.objects.all(), required=False, allow_null=True
    )
    has_user = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Client
        fields = (
            "id",
            "user_id",
            "has_user",
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
            "notes",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_has_user(self, obj):
        return bool(obj.user_id)

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        user = attrs.get("user", getattr(self.instance, "user", None))
        email = attrs.get("email", getattr(self.instance, "email", None))
        dni = attrs.get("dni", getattr(self.instance, "dni", None))

        if email:
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user and (not user or existing_user.pk != user.pk):
                raise serializers.ValidationError(
                    {"email": "Ya hay un usuario con ese email."}
                )
            conflict_client = (
                Client.objects.filter(email__iexact=email)
                .exclude(pk=getattr(self.instance, "pk", None))
                .filter(user__isnull=False)
                .first()
            )
            if conflict_client:
                raise serializers.ValidationError(
                    {"email": "Ya hay un usuario con ese email."}
                )

        if dni:
            conflict_dni = (
                Client.objects.filter(dni=dni)
                .exclude(pk=getattr(self.instance, "pk", None))
                .first()
            )
            if conflict_dni:
                message = (
                    "Ya hay un usuario con ese dni."
                    if conflict_dni.user_id
                    else "Ya hay un cliente con ese dni."
                )
                raise serializers.ValidationError({"dni": message})

        if user:
            other_client = (
                Client.objects.filter(user=user)
                .exclude(pk=getattr(self.instance, "pk", None))
                .first()
            )
            if other_client:
                raise serializers.ValidationError(
                    {"user_id": "Ese usuario ya tiene un cliente asociado."}
                )

        return attrs


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

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class UUIDSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)


class ModelCleanValidationMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        model_class = self.Meta.model
        instance = self.instance or model_class()
        for field, value in attrs.items():
            setattr(instance, field, value)

        try:
            instance.clean()
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict)
            raise serializers.ValidationError({"non_field_errors": exc.messages})

        return attrs

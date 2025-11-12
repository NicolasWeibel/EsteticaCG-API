from rest_framework import serializers


class UUIDSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)

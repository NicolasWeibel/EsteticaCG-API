from rest_framework import serializers

from ..models import ItemBenefit, ItemRecommendedPoint, ItemFAQ
from .base import UUIDSerializer


class ItemBenefitSerializer(UUIDSerializer):
    class Meta:
        model = ItemBenefit
        fields = ["id", "title", "detail", "order"]
        extra_kwargs = {"order": {"required": False}}


class ItemRecommendedPointSerializer(UUIDSerializer):
    class Meta:
        model = ItemRecommendedPoint
        fields = ["id", "title", "detail", "order"]
        extra_kwargs = {"order": {"required": False}}


class ItemFAQSerializer(UUIDSerializer):
    class Meta:
        model = ItemFAQ
        fields = ["id", "question", "answer", "order"]
        extra_kwargs = {"order": {"required": False}}
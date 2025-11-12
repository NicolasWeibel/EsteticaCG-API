from rest_framework import serializers
from ..models import Combo, ComboIngredient, ComboStep, ComboStepItem
from .base import UUIDSerializer


class ComboIngredientSerializer(UUIDSerializer):
    class Meta:
        model = ComboIngredient
        fields = "__all__"


class ComboStepItemSerializer(UUIDSerializer):
    class Meta:
        model = ComboStepItem
        fields = "__all__"


class ComboStepSerializer(UUIDSerializer):
    items = ComboStepItemSerializer(many=True, read_only=True)

    class Meta:
        model = ComboStep
        fields = "__all__"


class ComboSerializer(UUIDSerializer):
    ingredients = ComboIngredientSerializer(many=True, required=False)
    steps = ComboStepSerializer(many=True, required=False)

    class Meta:
        model = Combo
        fields = "__all__"

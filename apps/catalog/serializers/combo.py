from django.db import transaction
from ..models import Combo, ComboIngredient, ComboStep, ComboStepItem
from .base import UUIDSerializer


class ComboIngredientSerializer(UUIDSerializer):
    class Meta:
        model = ComboIngredient
        fields = "__all__"
        extra_kwargs = {"combo": {"read_only": True}}


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
    steps = ComboStepSerializer(many=True, required=False, read_only=True)

    class Meta:
        model = Combo
        fields = "__all__"

    def _save_ingredients(self, combo, ingredients):
        # Normaliza FK para aceptar UUID o objeto en el payload
        normalized = [
            {
                **ing,
                "treatment_zone_config": getattr(
                    ing.get("treatment_zone_config"),
                    "id",
                    ing.get("treatment_zone_config"),
                ),
            }
            for ing in ingredients
        ]
        ser = ComboIngredientSerializer(
            data=normalized, many=True, context=self.context
        )
        ser.is_valid(raise_exception=True)
        ser.save(combo=combo)

    def create(self, validated_data):
        ingredients = validated_data.pop("ingredients", [])
        with transaction.atomic():
            combo = super().create(validated_data)
            if ingredients:
                self._save_ingredients(combo, ingredients)
            return combo

    def update(self, instance, validated_data):
        ingredients = validated_data.pop("ingredients", None)
        with transaction.atomic():
            combo = super().update(instance, validated_data)
            if ingredients is not None:
                instance.ingredients.all().delete()
                if ingredients:
                    self._save_ingredients(instance, ingredients)
            return combo

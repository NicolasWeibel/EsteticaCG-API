from django.db import transaction
from rest_framework import serializers
from ..models import Combo, ComboIngredient, ComboStep, ComboStepItem, ComboImage
from .base import UUIDSerializer
from .gallery import ComboImageSerializer


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
    images = ComboImageSerializer(many=True, read_only=True)
    cover_image = serializers.SerializerMethodField()
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
    )

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

    def _create_images(self, combo, images):
        start = combo.images.count()
        to_create = []
        for index, img_file in enumerate(images, start=start):
            to_create.append(ComboImage(combo=combo, image=img_file, order=index))
        if to_create:
            ComboImage.objects.bulk_create(to_create)

    def get_cover_image(self, obj):
        first_img = obj.images.first()
        if first_img:
            return first_img.image.url
        return None

    def create(self, validated_data):
        ingredients = validated_data.pop("ingredients", [])
        uploaded_images = validated_data.pop("uploaded_images", [])
        with transaction.atomic():
            combo = super().create(validated_data)
            if uploaded_images:
                self._create_images(combo, uploaded_images)
            if ingredients:
                self._save_ingredients(combo, ingredients)
            return combo

    def update(self, instance, validated_data):
        ingredients = validated_data.pop("ingredients", None)
        uploaded_images = validated_data.pop("uploaded_images", [])
        with transaction.atomic():
            combo = super().update(instance, validated_data)
            if uploaded_images:
                self._create_images(combo, uploaded_images)
            if ingredients is not None:
                instance.ingredients.all().delete()
                if ingredients:
                    self._save_ingredients(instance, ingredients)
            return combo

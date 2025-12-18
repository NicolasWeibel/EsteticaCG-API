from rest_framework import serializers

from ..models import Journey, JourneyImage
from .base import UUIDSerializer
from .gallery import JourneyImageSerializer


class JourneySerializer(UUIDSerializer):
    images = JourneyImageSerializer(many=True, read_only=True)
    cover_image = serializers.SerializerMethodField()
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Journey
        fields = "__all__"

    def get_cover_image(self, obj):
        first_img = obj.images.first()
        if first_img:
            return first_img.image.url
        return None

    def _create_images(self, journey, images):
        start = journey.images.count()
        to_create = []
        for index, img_file in enumerate(images, start=start):
            to_create.append(JourneyImage(journey=journey, image=img_file, order=index))
        if to_create:
            JourneyImage.objects.bulk_create(to_create)

    def create(self, validated_data):
        uploaded_images = validated_data.pop("uploaded_images", [])
        journey = super().create(validated_data)
        if uploaded_images:
            self._create_images(journey, uploaded_images)
        return journey

    def update(self, instance, validated_data):
        uploaded_images = validated_data.pop("uploaded_images", [])
        journey = super().update(instance, validated_data)
        if uploaded_images:
            self._create_images(journey, uploaded_images)
        return journey

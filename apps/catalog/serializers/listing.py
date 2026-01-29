from rest_framework import serializers

from ..models import Treatment, Combo, Journey
from ..services.pricing import (
    price_pair_for_treatment,
    price_pair_for_combo,
    price_pair_for_journey,
    average_duration_for_treatment,
    duration_for_combo,
    duration_for_journey,
)


class FilterItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        img = getattr(obj, "image", None)
        if img:
            return img.url
        return None


class ZoneItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class BaseListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    slug = serializers.CharField()
    image = serializers.SerializerMethodField()
    title = serializers.CharField()
    short_description = serializers.CharField()
    description = serializers.CharField()
    price = serializers.SerializerMethodField()
    price_without_discount = serializers.SerializerMethodField()
    filters = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    journey = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    zones = serializers.SerializerMethodField()

    def get_image(self, obj):
        first = getattr(obj, "images", None)
        if first is not None:
            img = first.first()
            if img:
                return img.image.url
        return None

    def get_filters(self, obj):
        data = {
            "treatment_types": [],
            "objectives": [],
            "intensities": [],
            "tags": [],
        }
        if hasattr(obj, "treatment_types"):
            data["treatment_types"] = FilterItemSerializer(
                obj.treatment_types.all(), many=True
            ).data
        if hasattr(obj, "objectives"):
            data["objectives"] = FilterItemSerializer(obj.objectives.all(), many=True).data
        if hasattr(obj, "intensities"):
            data["intensities"] = FilterItemSerializer(
                obj.intensities.all(), many=True
            ).data
        if hasattr(obj, "tags"):
            data["tags"] = FilterItemSerializer(obj.tags.all(), many=True).data
        return data

    def get_journey(self, obj):
        journey = getattr(obj, "journey", None)
        if not journey:
            return None
        return {"id": journey.id, "title": journey.title, "slug": journey.slug}

    def get_category(self, obj):
        category = getattr(obj, "category", None)
        if not category:
            return None
        return {"id": category.id, "name": category.name, "slug": category.slug}

    def get_zones(self, obj):
        return []


class TreatmentListSerializer(BaseListItemSerializer):
    kind = serializers.SerializerMethodField()

    def get_kind(self, obj):
        return "treatment"

    def get_price(self, obj):
        return price_pair_for_treatment(obj)[0]

    def get_price_without_discount(self, obj):
        return price_pair_for_treatment(obj)[1]

    def get_duration(self, obj):
        return average_duration_for_treatment(obj)


class ComboListSerializer(BaseListItemSerializer):
    kind = serializers.SerializerMethodField()

    def get_kind(self, obj):
        return "combo"

    def get_price(self, obj):
        return price_pair_for_combo(obj)[0]

    def get_price_without_discount(self, obj):
        return price_pair_for_combo(obj)[1]

    def get_duration(self, obj):
        return duration_for_combo(obj)

    def get_zones(self, obj):
        zones = []
        seen = set()
        for ingredient in obj.ingredients.all():
            zone = getattr(ingredient.treatment_zone_config, "zone", None)
            if zone and zone.id not in seen:
                zones.append(zone)
                seen.add(zone.id)
        return ZoneItemSerializer(zones, many=True).data


class JourneyListSerializer(BaseListItemSerializer):
    kind = serializers.SerializerMethodField()

    def get_kind(self, obj):
        return "journey"

    def get_price(self, obj):
        return price_pair_for_journey(obj)[0]

    def get_price_without_discount(self, obj):
        return price_pair_for_journey(obj)[1]

    def get_duration(self, obj):
        return duration_for_journey(obj)

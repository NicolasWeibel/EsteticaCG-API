from rest_framework import serializers

from ..models import Placement, PlacementItem, Treatment, Combo, Journey
from .base import UUIDSerializer


class PlacementSerializer(UUIDSerializer):
    class Meta:
        model = Placement
        fields = "__all__"


class PlacementItemSerializer(UUIDSerializer):
    class Meta:
        model = PlacementItem
        fields = "__all__"

    def validate(self, attrs):
        placement = attrs.get("placement", self.instance.placement if self.instance else None)
        item_kind = attrs.get("item_kind", self.instance.item_kind if self.instance else None)
        item_id = attrs.get("item_id", self.instance.item_id if self.instance else None)

        if placement is None:
            raise serializers.ValidationError({"placement": "Placement is required."})

        item = self._get_item(item_kind, item_id)
        if item is None:
            raise serializers.ValidationError({"item_id": "Item not found."})

        if self.instance is None:
            current_count = placement.items.count()
            if current_count >= placement.max_items:
                raise serializers.ValidationError(
                    {"placement": "Placement item limit reached."}
                )
        return attrs

    def _get_item(self, kind, item_id):
        if kind == PlacementItem.ItemKind.TREATMENT:
            return Treatment.objects.filter(id=item_id).first()
        if kind == PlacementItem.ItemKind.COMBO:
            return Combo.objects.filter(id=item_id).first()
        if kind == PlacementItem.ItemKind.JOURNEY:
            return Journey.objects.filter(id=item_id).first()
        raise serializers.ValidationError({"item_kind": "Invalid item kind."})

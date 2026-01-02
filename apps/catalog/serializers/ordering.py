from rest_framework import serializers

from ..models import ItemOrder, Category, Journey, Treatment, Combo
from .base import UUIDSerializer


class ItemOrderSerializer(UUIDSerializer):
    class Meta:
        model = ItemOrder
        fields = "__all__"

    def validate(self, attrs):
        context_kind = attrs.get(
            "context_kind",
            self.instance.context_kind if self.instance else None,
        )
        context_id = attrs.get(
            "context_id",
            self.instance.context_id if self.instance else None,
        )
        item_kind = attrs.get(
            "item_kind",
            self.instance.item_kind if self.instance else None,
        )
        item_id = attrs.get(
            "item_id",
            self.instance.item_id if self.instance else None,
        )

        context = self._get_context(context_kind, context_id)
        item = self._get_item(item_kind, item_id)
        self._validate_item_in_context(context_kind, context, item_kind, item)
        return attrs

    def _get_context(self, kind, context_id):
        if kind == ItemOrder.ContextKind.CATEGORY:
            return Category.objects.filter(id=context_id).first()
        if kind == ItemOrder.ContextKind.JOURNEY:
            return Journey.objects.filter(id=context_id).first()
        raise serializers.ValidationError({"context_kind": "Invalid context kind."})

    def _get_item(self, kind, item_id):
        if kind == ItemOrder.ItemKind.TREATMENT:
            return Treatment.objects.filter(id=item_id).first()
        if kind == ItemOrder.ItemKind.COMBO:
            return Combo.objects.filter(id=item_id).first()
        if kind == ItemOrder.ItemKind.JOURNEY:
            return Journey.objects.filter(id=item_id).first()
        raise serializers.ValidationError({"item_kind": "Invalid item kind."})

    def _validate_item_in_context(self, context_kind, context, item_kind, item):
        if context is None:
            raise serializers.ValidationError({"context_id": "Context not found."})
        if item is None:
            raise serializers.ValidationError({"item_id": "Item not found."})

        if context_kind == ItemOrder.ContextKind.CATEGORY:
            if item_kind == ItemOrder.ItemKind.JOURNEY:
                if item.category_id != context.id:
                    raise serializers.ValidationError(
                        {"item_id": "Journey must belong to the category."}
                    )
            else:
                if item.category_id != context.id:
                    raise serializers.ValidationError(
                        {"item_id": "Item must belong to the category."}
                    )
        elif context_kind == ItemOrder.ContextKind.JOURNEY:
            if item_kind == ItemOrder.ItemKind.JOURNEY:
                raise serializers.ValidationError(
                    {"item_kind": "Journeys are not valid items in a journey."}
                )
            if item.journey_id != context.id:
                raise serializers.ValidationError(
                    {"item_id": "Item must belong to the journey."}
                )

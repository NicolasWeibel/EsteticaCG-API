from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..models import ItemOrder, Category, Journey, Treatment, Combo
from ..permissions import IsAdminOrReadOnly
from ..serializers import ItemOrderSerializer


ITEM_KIND_MODELS = {
    ItemOrder.ItemKind.TREATMENT: Treatment,
    ItemOrder.ItemKind.COMBO: Combo,
    ItemOrder.ItemKind.JOURNEY: Journey,
}

CONTEXT_KIND_MODELS = {
    ItemOrder.ContextKind.CATEGORY: Category,
    ItemOrder.ContextKind.JOURNEY: Journey,
}


class ItemOrderViewSet(viewsets.ModelViewSet):
    queryset = ItemOrder.objects.all().order_by("order")
    serializer_class = ItemOrderSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["context_kind", "context_id"]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        context_kind = request.data.get("context_kind")
        context_id = request.data.get("context_id")
        items = request.data.get("items", [])

        if context_kind not in CONTEXT_KIND_MODELS:
            raise ValidationError({"context_kind": "Invalid context kind."})
        if not context_id:
            raise ValidationError({"context_id": "Context id is required."})
        if not isinstance(items, list):
            raise ValidationError({"items": "Items must be a list."})

        context_model = CONTEXT_KIND_MODELS[context_kind]
        context = context_model.objects.filter(id=context_id).first()
        if context is None:
            raise ValidationError({"context_id": "Context not found."})

        items_data = self._collect_items(items)
        self._validate_items_in_context(context_kind, context, items_data)

        existing_qs = ItemOrder.objects.filter(
            context_kind=context_kind, context_id=context_id
        )
        existing_map = {
            (o.item_kind, str(o.item_id)): o for o in existing_qs
        }

        keep_ids = []
        to_create = []
        to_update = []

        for order, (item_kind, item_id) in enumerate(items_data):
            key = (item_kind, item_id)
            existing = existing_map.get(key)
            if existing:
                keep_ids.append(existing.id)
                if existing.order != order:
                    existing.order = order
                    to_update.append(existing)
            else:
                to_create.append(
                    ItemOrder(
                        context_kind=context_kind,
                        context_id=context_id,
                        item_kind=item_kind,
                        item_id=item_id,
                        order=order,
                    )
                )

        if keep_ids:
            existing_qs.exclude(id__in=keep_ids).delete()
        else:
            existing_qs.delete()

        if to_create:
            ItemOrder.objects.bulk_create(to_create)
        if to_update:
            ItemOrder.objects.bulk_update(to_update, ["order"])

        ordered_qs = ItemOrder.objects.filter(
            context_kind=context_kind, context_id=context_id
        ).order_by("order")
        serializer = self.get_serializer(ordered_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _collect_items(self, items):
        seen = set()
        items_data = []
        ids_by_kind = {}

        for item in items:
            if not isinstance(item, dict):
                raise ValidationError({"items": "Each item must be an object."})
            item_kind = item.get("item_kind")
            item_id = item.get("item_id")
            if item_kind not in ITEM_KIND_MODELS:
                raise ValidationError({"item_kind": "Invalid item kind."})
            if not item_id:
                raise ValidationError({"item_id": "Item id is required."})
            key = (item_kind, str(item_id))
            if key in seen:
                raise ValidationError({"items": "Duplicate items are not allowed."})
            seen.add(key)
            items_data.append(key)
            ids_by_kind.setdefault(item_kind, []).append(item_id)

        item_map = {}
        for kind, ids in ids_by_kind.items():
            model = ITEM_KIND_MODELS[kind]
            for obj in model.objects.filter(id__in=ids):
                item_map[(kind, str(obj.id))] = obj

        for key in items_data:
            if key not in item_map:
                raise ValidationError({"items": f"Item not found: {key[1]}"})

        self._item_map = item_map
        return items_data

    def _validate_items_in_context(self, context_kind, context, items_data):
        for item_kind, item_id in items_data:
            item = self._item_map[(item_kind, item_id)]
            if context_kind == ItemOrder.ContextKind.CATEGORY:
                if item_kind == ItemOrder.ItemKind.JOURNEY:
                    if item.category_id != context.id:
                        raise ValidationError(
                            {"items": "Journey must belong to the category."}
                        )
                else:
                    if item.category_id != context.id:
                        raise ValidationError(
                            {"items": "Item must belong to the category."}
                        )
            elif context_kind == ItemOrder.ContextKind.JOURNEY:
                if item_kind == ItemOrder.ItemKind.JOURNEY:
                    raise ValidationError(
                        {"items": "Journeys are not valid items in a journey."}
                    )
                if item.journey_id != context.id:
                    raise ValidationError(
                        {"items": "Item must belong to the journey."}
                    )

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..models import Placement, PlacementItem, Treatment, Combo, Journey
from ..permissions import IsAdminOrReadOnly
from ..serializers import PlacementSerializer, PlacementItemSerializer
from ..services.listing import serialize_items


ITEM_KIND_MODELS = {
    PlacementItem.ItemKind.TREATMENT: Treatment,
    PlacementItem.ItemKind.COMBO: Combo,
    PlacementItem.ItemKind.JOURNEY: Journey,
}


class PlacementViewSet(viewsets.ModelViewSet):
    queryset = Placement.objects.all().order_by("title")
    serializer_class = PlacementSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    filterset_fields = ["slug", "is_active"]

    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request, slug=None):
        placement = self.get_object()
        items_qs = placement.items.order_by("order")
        items = self._resolve_items(items_qs)
        return Response(
            {
                "placement": self.get_serializer(placement).data,
                "items": serialize_items(items, context=self.get_serializer_context()),
            }
        )

    @action(detail=True, methods=["post"], url_path="reorder-items")
    def reorder_items(self, request, slug=None):
        placement = self.get_object()
        items = request.data.get("items", [])
        if not isinstance(items, list):
            raise ValidationError({"items": "Items must be a list."})
        if len(items) > placement.max_items:
            raise ValidationError({"items": "Placement item limit exceeded."})

        items_data = self._collect_items(items)

        existing_qs = PlacementItem.objects.filter(placement=placement)
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
                    PlacementItem(
                        placement=placement,
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
            PlacementItem.objects.bulk_create(to_create)
        if to_update:
            PlacementItem.objects.bulk_update(to_update, ["order"])

        items_qs = placement.items.order_by("order")
        items = self._resolve_items(items_qs)
        return Response(
            {
                "placement": self.get_serializer(placement).data,
                "items": serialize_items(items, context=self.get_serializer_context()),
            },
            status=status.HTTP_200_OK,
        )

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

        return items_data

    def _resolve_items(self, items_qs):
        items = []
        ids_by_kind = {}
        for item in items_qs:
            ids_by_kind.setdefault(item.item_kind, []).append(item.item_id)

        item_map = {}
        for kind, ids in ids_by_kind.items():
            model = ITEM_KIND_MODELS.get(kind)
            if not model:
                continue
            for obj in model.objects.filter(id__in=ids):
                item_map[(kind, str(obj.id))] = obj

        for item in items_qs:
            key = (item.item_kind, str(item.item_id))
            obj = item_map.get(key)
            if obj:
                items.append(obj)
        return items


class PlacementItemViewSet(viewsets.ModelViewSet):
    queryset = PlacementItem.objects.all().order_by("order")
    serializer_class = PlacementItemSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["placement", "item_kind"]

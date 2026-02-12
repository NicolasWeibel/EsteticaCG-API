from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..models import Category, Treatment, Combo, Journey, ItemOrder
from ..serializers import CategorySerializer
from ..permissions import IsAdminOrReadOnly
from ..services.listing import SORT_OPTIONS, sort_items, serialize_items
from ..services.filters_summary import build_filters_summary


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request, pk=None):
        category = self.get_object()
        sort_key = request.query_params.get("sort") or category.default_sort
        if sort_key == "most_sold":
            raise ValidationError({"sort": "most_sold is not available yet."})
        if sort_key not in SORT_OPTIONS:
            sort_key = "price_asc"

        treatments = Treatment.objects.filter(
            category=category, is_active=True
        ).prefetch_related(
            "media",
            "zone_configs",
            "treatment_types",
            "objectives",
            "intensities",
            "tags",
        )
        combos = Combo.objects.filter(category=category, is_active=True).prefetch_related(
            "media",
            "ingredients__treatment_zone_config__zone",
            "treatment_types",
            "objectives",
            "intensities",
            "tags",
        )
        journeys = Journey.objects.filter(category=category).prefetch_related(
            "media",
            "treatments__zone_configs",
            "treatments__media",
            "treatments__treatment_types",
            "treatments__objectives",
            "treatments__intensities",
            "treatments__tags",
            "combos",
            "combos__media",
            "combos__ingredients__treatment_zone_config__zone",
            "combos__treatment_types",
            "combos__objectives",
            "combos__intensities",
            "combos__tags",
        )

        orders = ItemOrder.objects.filter(
            context_kind=ItemOrder.ContextKind.CATEGORY, context_id=category.id
        )
        order_map = {(o.item_kind, str(o.item_id)): o.order for o in orders}

        product_items = sort_items(list(treatments) + list(combos), sort_key, order_map)
        journey_items = sort_items(list(journeys), sort_key, order_map)

        if category.include_journeys:
            if category.journey_position == Category.JourneyPosition.FIRST:
                items = journey_items + product_items
            else:
                items = product_items + journey_items
        else:
            items = product_items

        return Response(
            {
                "items": serialize_items(items, context=self.get_serializer_context()),
                "filters": build_filters_summary(category=category),
                "include_journeys": category.include_journeys,
                "journey_position": category.journey_position,
                "sort": sort_key,
            }
        )

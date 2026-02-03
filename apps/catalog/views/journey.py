from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..models import Journey, Treatment, Combo, ItemOrder
from ..serializers import JourneySerializer, JourneyImageSerializer
from ..permissions import IsAdminOrReadOnly
from .mixins import GalleryOrderingMixin, MultipartJsonMixin
from ..services.listing import SORT_OPTIONS, sort_items, serialize_items
from ..services.filters_summary import build_filters_summary


class JourneyViewSet(MultipartJsonMixin, GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = Journey.objects.prefetch_related("images").order_by("title")
    serializer_class = JourneySerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    image_serializer_class = JourneyImageSerializer
    multipart_json_fields = ["addons"]
    filterset_fields = ["category"]

    @action(detail=True, methods=["post"], url_path="reorder-images")
    def reorder_images(self, request, pk=None):
        ordered_ids = request.data.get("ordered_ids", [])
        journey = self.get_object()
        return self._reorder_images(journey, ordered_ids)

    @action(detail=True, methods=["get"], url_path="images")
    def images(self, request, pk=None):
        journey = self.get_object()
        images = journey.images.order_by("order")
        return Response(self.image_serializer_class(images, many=True).data)

    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request, pk=None):
        journey = self.get_object()
        sort_key = request.query_params.get("sort") or journey.default_sort
        if sort_key == "most_sold":
            raise ValidationError({"sort": "most_sold is not available yet."})
        if sort_key not in SORT_OPTIONS:
            sort_key = "price_asc"

        treatments = Treatment.objects.filter(journey=journey).prefetch_related(
            "images",
            "zone_configs",
            "treatment_types",
            "objectives",
            "intensities",
            "tags",
        )
        combos = Combo.objects.filter(journey=journey).prefetch_related(
            "images",
            "ingredients__treatment_zone_config__zone",
            "treatment_types",
            "objectives",
            "intensities",
            "tags",
        )

        orders = ItemOrder.objects.filter(
            context_kind=ItemOrder.ContextKind.JOURNEY, context_id=journey.id
        )
        order_map = {(o.item_kind, str(o.item_id)): o.order for o in orders}

        items = sort_items(list(treatments) + list(combos), sort_key, order_map)

        return Response(
            {
                "items": serialize_items(items, context=self.get_serializer_context()),
                "filters": build_filters_summary(journey=journey),
                "sort": sort_key,
            }
        )

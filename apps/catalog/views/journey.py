from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..models import Journey, Treatment, Combo, ItemOrder
from ..serializers import JourneySerializer, PublicJourneySerializer, JourneyMediaSerializer
from ..permissions import IsAdminOrReadOnly
from .mixins import GalleryOrderingMixin, MultipartJsonMixin
from ..services.listing import SORT_OPTIONS, sort_items, serialize_items
from ..services.filters_summary import build_filters_summary


class JourneyViewSet(MultipartJsonMixin, GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = (
        Journey.objects.select_related("category")
        .prefetch_related("media")
        .order_by("title")
    )
    serializer_class = JourneySerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    media_serializer_class = JourneyMediaSerializer
    multipart_json_fields = ["addons"]
    filterset_fields = ["category"]

    def get_serializer_class(self):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return JourneySerializer
        return PublicJourneySerializer

    @action(detail=True, methods=["post"], url_path="reorder-media")
    def reorder_media(self, request, pk=None):
        ordered_ids = request.data.get("ordered_media_ids", [])
        journey = self.get_object()
        return self._reorder_media(journey, ordered_ids)

    @action(detail=True, methods=["get"], url_path="media")
    def media(self, request, pk=None):
        journey = self.get_object()
        media_items = journey.media.order_by("order")
        return Response(self.media_serializer_class(media_items, many=True).data)

    @action(detail=True, methods=["get"], url_path="items")
    def items(self, request, pk=None):
        journey = self.get_object()
        sort_key = request.query_params.get("sort") or journey.default_sort
        if sort_key == "most_sold":
            raise ValidationError({"sort": "most_sold is not available yet."})
        if sort_key not in SORT_OPTIONS:
            sort_key = "price_asc"

        treatments = Treatment.objects.filter(journey=journey).prefetch_related(
            "media",
            "zone_configs",
            "treatment_types",
            "objectives",
            "intensities",
            "tags",
        )
        combos = Combo.objects.filter(journey=journey).prefetch_related(
            "media",
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

    @action(detail=False, methods=["get"], url_path=r"by-slug/(?P<slug>[^/.]+)")
    def by_slug(self, request, slug=None):
        journey = get_object_or_404(self.get_queryset(), slug=slug)
        return Response(self.get_serializer(journey).data)

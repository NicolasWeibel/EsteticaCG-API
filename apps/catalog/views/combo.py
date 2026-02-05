from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from ..models import Combo
from ..serializers import ComboSerializer, PublicComboSerializer, ComboImageSerializer
from ..permissions import IsAdminOrReadOnly
from .mixins import GalleryOrderingMixin, MultipartJsonMixin


class ComboViewSet(MultipartJsonMixin, GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = Combo.objects.prefetch_related(
        "images",
        "tags",
        "benefits",
        "recommended_points",
        "faqs",
        "session_items",
        "session_items__ingredient",
        "session_items__ingredient__treatment_zone_config",
        "session_items__ingredient__treatment_zone_config__zone",
    ).order_by("-title")
    serializer_class = ComboSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    image_serializer_class = ComboImageSerializer
    multipart_json_fields = [
        "ingredients",
        "session_items",
        "benefits",
        "recommended_points",
        "faqs",
    ]
    filterset_fields = [
        "category",
        "journey",
        "sessions",
        "min_session_interval_days",
    ]
    search_fields = ["title", "description"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = getattr(self.request, "user", None)
        if not (user and user.is_staff):
            qs = qs.filter(is_active=True)
        return qs

    def get_serializer_class(self):
        user = getattr(self.request, "user", None)
        if user and user.is_staff:
            return ComboSerializer
        return PublicComboSerializer

    @action(detail=True, methods=["post"], url_path="reorder-images")
    def reorder_images(self, request, pk=None):
        ordered_ids = request.data.get("ordered_ids", [])
        combo = self.get_object()
        return self._reorder_images(combo, ordered_ids)

    @action(detail=True, methods=["get"], url_path="images")
    def images(self, request, pk=None):
        combo = self.get_object()
        images = combo.images.order_by("order")
        return Response(self.image_serializer_class(images, many=True).data)

    @action(detail=False, methods=["get"], url_path=r"by-slug/(?P<slug>[^/.]+)")
    def by_slug(self, request, slug=None):
        combo = get_object_or_404(self.get_queryset(), slug=slug)
        return Response(self.get_serializer(combo).data)

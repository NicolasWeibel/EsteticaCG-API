from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from ..models import Combo
from ..serializers import ComboSerializer, ComboImageSerializer
from ..permissions import IsAdminOrReadOnly
from .mixins import GalleryOrderingMixin, MultipartJsonMixin


class ComboViewSet(MultipartJsonMixin, GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = Combo.objects.prefetch_related(
        "images",
        "tags",
        "benefits",
        "recommended_points",
        "faqs",
    ).order_by("-title")
    serializer_class = ComboSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    image_serializer_class = ComboImageSerializer
    multipart_json_fields = [
        "ingredients",
        "steps",
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

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from ..models import Combo
from ..serializers import ComboSerializer, ComboImageSerializer
from ..permissions import IsAdminOrReadOnly
from .mixins import GalleryOrderingMixin


class ComboViewSet(GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = Combo.objects.prefetch_related("images").order_by("-title")
    serializer_class = ComboSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    image_serializer_class = ComboImageSerializer
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

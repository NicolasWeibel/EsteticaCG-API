from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from ..models import Journey
from ..serializers import JourneySerializer, JourneyImageSerializer
from ..permissions import IsAdminOrReadOnly
from .mixins import GalleryOrderingMixin


class JourneyViewSet(GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = Journey.objects.prefetch_related("images").order_by("title")
    serializer_class = JourneySerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    image_serializer_class = JourneyImageSerializer
    filterset_fields = ["category"]

    @action(detail=True, methods=["post"], url_path="reorder-images")
    def reorder_images(self, request, pk=None):
        ordered_ids = request.data.get("ordered_ids", [])
        journey = self.get_object()
        return self._reorder_images(journey, ordered_ids)

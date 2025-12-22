from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from ..permissions import IsAdminOrReadOnly
from ..models import Treatment
from ..serializers import TreatmentSerializer, TreatmentImageSerializer
from .mixins import GalleryOrderingMixin, MultipartJsonMixin


class TreatmentViewSet(MultipartJsonMixin, GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = Treatment.objects.prefetch_related("images").order_by("-title")
    serializer_class = TreatmentSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    image_serializer_class = TreatmentImageSerializer
    multipart_json_fields = ["zone_configs"]
    filterset_fields = ["category", "journey"]
    search_fields = ["title", "description"]

    @action(detail=True, methods=["post"], url_path="reorder-images")
    def reorder_images(self, request, pk=None):
        ordered_ids = request.data.get("ordered_ids", [])
        treatment = self.get_object()
        return self._reorder_images(treatment, ordered_ids)

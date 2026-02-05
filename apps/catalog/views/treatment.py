from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from django.db.models import Avg
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from ..permissions import IsAdminOrReadOnly
from ..models import Treatment
from ..serializers import (
    TreatmentSerializer,
    PublicTreatmentSerializer,
    TreatmentImageSerializer,
)
from .mixins import GalleryOrderingMixin, MultipartJsonMixin


class TreatmentViewSet(MultipartJsonMixin, GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = (
        Treatment.objects.annotate(avg_duration=Avg("zone_configs__duration"))
        .select_related("category", "journey")
        .prefetch_related(
            "images",
            "tags",
            "benefits",
            "recommended_points",
            "faqs",
            "zone_configs",
            "zone_configs__zone",
        )
        .order_by("-title")
    )
    serializer_class = TreatmentSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    image_serializer_class = TreatmentImageSerializer
    multipart_json_fields = ["zone_configs", "benefits", "recommended_points", "faqs"]
    filterset_fields = ["category", "journey"]
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
            return TreatmentSerializer
        return PublicTreatmentSerializer

    @action(detail=True, methods=["post"], url_path="reorder-images")
    def reorder_images(self, request, pk=None):
        ordered_ids = request.data.get("ordered_ids", [])
        treatment = self.get_object()
        return self._reorder_images(treatment, ordered_ids)

    @action(detail=True, methods=["get"], url_path="images")
    def images(self, request, pk=None):
        treatment = self.get_object()
        images = treatment.images.order_by("order")
        return Response(self.image_serializer_class(images, many=True).data)

    @action(detail=False, methods=["get"], url_path=r"by-slug/(?P<slug>[^/.]+)")
    def by_slug(self, request, slug=None):
        treatment = get_object_or_404(self.get_queryset(), slug=slug)
        return Response(self.get_serializer(treatment).data)

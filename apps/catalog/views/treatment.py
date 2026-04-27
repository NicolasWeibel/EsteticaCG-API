from rest_framework import viewsets
from django.db.models import Avg, Min
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from ..permissions import IsAdminOrReadOnly
from ..models import Treatment
from ..serializers import (
    TreatmentSerializer,
    PublicTreatmentSerializer,
    TreatmentMediaSerializer,
)
from .mixins import GalleryOrderingMixin


class TreatmentViewSet(GalleryOrderingMixin, viewsets.ModelViewSet):
    queryset = (
        Treatment.objects.annotate(
            avg_duration=Avg("zone_configs__duration"),
            min_duration=Min("zone_configs__duration"),
        )
        .select_related("category", "journey")
        .prefetch_related(
            "media",
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
    media_serializer_class = TreatmentMediaSerializer
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

    @action(detail=True, methods=["post"], url_path="reorder-media")
    def reorder_media(self, request, pk=None):
        ordered_ids = request.data.get("ordered_media_ids", [])
        treatment = self.get_object()
        return self._reorder_media(treatment, ordered_ids)

    @action(detail=True, methods=["get"], url_path="media")
    def media(self, request, pk=None):
        treatment = self.get_object()
        media_items = treatment.media.order_by("order")
        return Response(self.media_serializer_class(media_items, many=True).data)

    @action(detail=False, methods=["get"], url_path=r"by-slug/(?P<slug>[^/.]+)")
    def by_slug(self, request, slug=None):
        category_slug = request.query_params.get("category")
        category_id = request.query_params.get("category_id")
        qs = self.get_queryset().filter(slug__iexact=slug)
        if category_slug:
            qs = qs.filter(category__slug__iexact=category_slug)
        elif category_id:
            qs = qs.filter(category_id=category_id)
        count = qs.count()
        if count == 0:
            raise NotFound(detail="No encontrado.")
        if count > 1:
            raise ValidationError(
                {
                    "slug": [
                        "Hay más de un resultado para este slug. Envíe category o category_id."
                    ]
                }
            )
        treatment = qs.first()
        return Response(self.get_serializer(treatment).data)

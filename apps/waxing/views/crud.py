from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from ..models import (
    Area,
    AreaCategory,
    BenefitItem,
    FaqItem,
    FeaturedItemOrder,
    Pack,
    PackArea,
    RecommendationItem,
    Section,
    WaxingContent,
    WaxingSettings,
)
from ..permissions import IsAdminOrReadOnly
from ..serializers import (
    AreaCategorySerializer,
    AreaSerializer,
    BenefitItemSerializer,
    FaqItemSerializer,
    FeaturedItemOrderSerializer,
    PackAreaSerializer,
    PackSerializer,
    RecommendationItemSerializer,
    SectionSerializer,
    WaxingContentSerializer,
    WaxingSettingsSerializer,
)
from .mixins import MultipartJsonMixin


class WaxingSettingsViewSet(viewsets.ModelViewSet):
    queryset = WaxingSettings.objects.all().order_by("created_at")
    serializer_class = WaxingSettingsSerializer
    permission_classes = [IsAdminOrReadOnly]


class SectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.all().order_by("-created_at")
    serializer_class = SectionSerializer
    permission_classes = [IsAdminOrReadOnly]


class AreaCategoryViewSet(viewsets.ModelViewSet):
    queryset = AreaCategory.objects.select_related("section").all().order_by("order")
    serializer_class = AreaCategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ("section", "is_active")


class AreaViewSet(viewsets.ModelViewSet):
    queryset = (
        Area.objects.select_related("section", "category")
        .all()
        .order_by("order", "name")
    )
    serializer_class = AreaSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ("section", "category", "is_active", "is_featured")


class PackViewSet(viewsets.ModelViewSet):
    queryset = (
        Pack.objects.select_related("section")
        .prefetch_related("pack_areas", "pack_areas__area")
        .all()
        .order_by("order", "name")
    )
    serializer_class = PackSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ("section", "is_active", "is_featured")


class PackAreaViewSet(viewsets.ModelViewSet):
    queryset = (
        PackArea.objects.select_related("pack", "area", "area__category")
        .all()
        .order_by("order")
    )
    serializer_class = PackAreaSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ("pack", "area")


class FeaturedItemOrderViewSet(viewsets.ModelViewSet):
    queryset = FeaturedItemOrder.objects.select_related("section").all().order_by("order")
    serializer_class = FeaturedItemOrderSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ("section", "item_kind")


class WaxingContentViewSet(MultipartJsonMixin, viewsets.ModelViewSet):
    queryset = WaxingContent.objects.all().order_by("created_at")
    serializer_class = WaxingContentSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    multipart_json_fields = [
        "benefits",
        "recommendations",
        "faqs",
        "benefits_remove_ids",
        "recommendations_remove_ids",
        "faqs_remove_ids",
    ]


class BenefitItemViewSet(viewsets.ModelViewSet):
    queryset = BenefitItem.objects.select_related("content").all().order_by("order")
    serializer_class = BenefitItemSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ("content", "is_active")


class RecommendationItemViewSet(viewsets.ModelViewSet):
    queryset = RecommendationItem.objects.select_related("content").all().order_by("order")
    serializer_class = RecommendationItemSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ("content", "is_active")


class FaqItemViewSet(viewsets.ModelViewSet):
    queryset = FaqItem.objects.select_related("content").all().order_by("order")
    serializer_class = FaqItemSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ("content", "is_active")

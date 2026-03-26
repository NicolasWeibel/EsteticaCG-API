from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

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


class WaxingSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        settings_qs = WaxingSettings.objects.all().order_by("created_at")
        sections_qs = Section.objects.all().order_by("-created_at")
        area_categories_qs = (
            AreaCategory.objects.select_related("section").all().order_by("order", "name")
        )
        areas_qs = (
            Area.objects.select_related("section", "category")
            .all()
            .order_by("order", "name")
        )
        packs_qs = Pack.objects.select_related("section").all().order_by("order", "name")
        pack_areas_qs = (
            PackArea.objects.select_related("pack", "area", "area__category")
            .all()
            .order_by("order")
        )
        featured_orders_qs = (
            FeaturedItemOrder.objects.select_related("section").all().order_by("order")
        )
        content_qs = (
            WaxingContent.objects.prefetch_related(
                "benefits",
                "recommendations",
                "faqs",
            )
            .all()
            .order_by("created_at")
        )
        benefits_qs = BenefitItem.objects.select_related("content").all().order_by("order")
        recommendations_qs = (
            RecommendationItem.objects.select_related("content").all().order_by("order")
        )
        faqs_qs = FaqItem.objects.select_related("content").all().order_by("order")

        return Response(
            {
                "settings": WaxingSettingsSerializer(settings_qs, many=True).data,
                "sections": SectionSerializer(sections_qs, many=True).data,
                "area_categories": AreaCategorySerializer(
                    area_categories_qs, many=True
                ).data,
                "areas": AreaSerializer(areas_qs, many=True).data,
                "packs": PackSerializer(packs_qs, many=True).data,
                "pack_areas": PackAreaSerializer(pack_areas_qs, many=True).data,
                "featured_orders": FeaturedItemOrderSerializer(
                    featured_orders_qs, many=True
                ).data,
                "content": WaxingContentSerializer(content_qs, many=True).data,
                "benefits": BenefitItemSerializer(benefits_qs, many=True).data,
                "recommendations": RecommendationItemSerializer(
                    recommendations_qs, many=True
                ).data,
                "faqs": FaqItemSerializer(faqs_qs, many=True).data,
            }
        )

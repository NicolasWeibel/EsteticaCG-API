from django.urls import path
from rest_framework.routers import DefaultRouter

from ...views import (
    AreaCategoryViewSet,
    AreaViewSet,
    BenefitItemViewSet,
    CategoryAreaReorderView,
    CategoryPackReorderView,
    FaqItemViewSet,
    FeaturedItemOrderViewSet,
    PackAreaViewSet,
    PackViewSet,
    RecommendationItemViewSet,
    SectionFeaturedReorderView,
    SectionViewSet,
    WaxingContentViewSet,
    WaxingPublicSummaryView,
    WaxingPublicView,
    WaxingSummaryView,
    WaxingSettingsViewSet,
)

app_name = "waxing"

router = DefaultRouter()
router.register(r"settings", WaxingSettingsViewSet)
router.register(r"sections", SectionViewSet)
router.register(r"area_categories", AreaCategoryViewSet)
router.register(r"areas", AreaViewSet)
router.register(r"packs", PackViewSet)
router.register(r"pack_areas", PackAreaViewSet)
router.register(r"featured_orders", FeaturedItemOrderViewSet)
router.register(r"content", WaxingContentViewSet)
router.register(r"benefits", BenefitItemViewSet)
router.register(r"recommendations", RecommendationItemViewSet)
router.register(r"faqs", FaqItemViewSet)

urlpatterns = [
    path("", WaxingPublicView.as_view(), name="summary"),
    path("summary/", WaxingPublicSummaryView.as_view(), name="summary-minimal"),
    path("waxing/", WaxingSummaryView.as_view(), name="waxing-summary"),
    path(
        "categories/<uuid:category_id>/areas/reorder/",
        CategoryAreaReorderView.as_view(),
        name="category-areas-reorder",
    ),
    path(
        "categories/<uuid:category_id>/packs/reorder/",
        CategoryPackReorderView.as_view(),
        name="category-packs-reorder",
    ),
    path(
        "sections/<uuid:section_id>/featured/reorder/",
        SectionFeaturedReorderView.as_view(),
        name="section-featured-reorder",
    ),
] + router.urls

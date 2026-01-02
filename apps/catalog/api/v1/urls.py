from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.catalog.views.catalog import CatalogSummaryView
from apps.catalog.views.treatment import TreatmentViewSet
from apps.catalog.views.combo import ComboViewSet
from apps.catalog.views.journey import JourneyViewSet
from apps.catalog.views.gallery import (
    TreatmentImageViewSet,
    ComboImageViewSet,
    JourneyImageViewSet,
)
from apps.catalog.views.category import CategoryViewSet
from apps.catalog.views.ordering import ItemOrderViewSet
from apps.catalog.views.placement import PlacementViewSet, PlacementItemViewSet
from apps.catalog.views.zone import ZoneViewSet
from apps.catalog.views.treatmentzoneconfig import TreatmentZoneConfigViewSet
from apps.catalog.views.incompatibility import TreatmentZoneIncompatibilityViewSet
from apps.catalog.views.filters import (
    TreatmentTypeViewSet,
    ObjectiveViewSet,
    IntensityLevelViewSet,
    DurationBucketViewSet,
    TagViewSet,
)

router = DefaultRouter()
router.register(r"treatments", TreatmentViewSet)
router.register(r"treatment-images", TreatmentImageViewSet)
router.register(r"combos", ComboViewSet)
router.register(r"combo-images", ComboImageViewSet)
router.register(r"journeys", JourneyViewSet)
router.register(r"journey-images", JourneyImageViewSet)
router.register(r"categories", CategoryViewSet)
router.register(r"orders", ItemOrderViewSet)
router.register(r"placements", PlacementViewSet)
router.register(r"placement-items", PlacementItemViewSet)
router.register(r"zones", ZoneViewSet)
router.register(r"zone-configs", TreatmentZoneConfigViewSet)
router.register(r"incompatibilities", TreatmentZoneIncompatibilityViewSet)

# Filtros
router.register(r"filters/treatment-type", TreatmentTypeViewSet)
router.register(r"filters/objectives", ObjectiveViewSet)
router.register(r"filters/intensities", IntensityLevelViewSet)
router.register(r"filters/duration", DurationBucketViewSet)
router.register(r"filters/tags", TagViewSet)

urlpatterns = router.urls + [
    path("catalog/", CatalogSummaryView.as_view(), name="catalog-summary"),
]

from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.catalog.views.catalog import CatalogSummaryView
from apps.catalog.views.treatment import TreatmentViewSet
from apps.catalog.views.combo import ComboViewSet
from apps.catalog.views.journey import JourneyViewSet
from apps.catalog.views.zone import ZoneViewSet
from apps.catalog.views.treatmentzoneconfig import TreatmentZoneConfigViewSet
from apps.catalog.views.incompatibility import TreatmentZoneIncompatibilityViewSet
from apps.catalog.views.filters import (
    TreatmentTypeViewSet,
    ObjectiveViewSet,
    IntensityLevelViewSet,
    DurationBucketViewSet,
)

router = DefaultRouter()
router.register(r"treatments", TreatmentViewSet)
router.register(r"combos", ComboViewSet)
router.register(r"journeys", JourneyViewSet)
router.register(r"zones", ZoneViewSet)
router.register(r"zone-configs", TreatmentZoneConfigViewSet)
router.register(r"incompatibilities", TreatmentZoneIncompatibilityViewSet)

# Filtros
router.register(r"filters/treatment-type", TreatmentTypeViewSet)
router.register(r"filters/objectives", ObjectiveViewSet)
router.register(r"filters/intensities", IntensityLevelViewSet)
router.register(r"filters/duration", DurationBucketViewSet)

urlpatterns = router.urls + [
    path("catalog/", CatalogSummaryView.as_view(), name="catalog-summary"),
]

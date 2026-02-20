from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from apps.catalog.models import (
    Treatment,
    Combo,
    Journey,
    Category,
    Zone,
    Technique,
    Objective,
    Intensity,
)
from apps.catalog.serializers import (
    TreatmentSerializer,
    ComboSerializer,
    JourneySerializer,
    CategorySerializer,
    ZoneSerializer,
    TechniqueSerializer,
    ObjectiveSerializer,
    IntensitySerializer,
)


class CatalogSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        treatments_qs = (
            Treatment.objects.all()
            .select_related("category", "journey")
            .prefetch_related(
                "media",
                "tags",
                "techniques",
                "objectives",
                "intensities",
                "zone_configs",
                "zone_configs__zone",
                "benefits",
                "recommended_points",
                "faqs",
            )
        )
        combos_qs = (
            Combo.objects.all()
            .select_related("category", "journey")
            .prefetch_related(
                "media",
                "tags",
                "techniques",
                "objectives",
                "intensities",
                "ingredients",
                "ingredients__treatment_zone_config",
                "ingredients__treatment_zone_config__zone",
                "ingredients__treatment_zone_config__treatment",
                "session_items",
                "session_items__ingredient",
                "session_items__ingredient__treatment_zone_config",
                "session_items__ingredient__treatment_zone_config__zone",
                "session_items__ingredient__treatment_zone_config__treatment",
                "benefits",
                "recommended_points",
                "faqs",
            )
        )
        journeys_qs = (
            Journey.objects.all()
            .select_related("category")
            .prefetch_related(
                "media",
                "addons",
                "benefits",
                "recommended_points",
                "faqs",
            )
        )
        categories_qs = Category.objects.all()
        zones_qs = Zone.objects.all()
        techniques_qs = Technique.objects.all()
        objectives_qs = Objective.objects.all()
        intensities_qs = Intensity.objects.all()

        treatments = TreatmentSerializer(treatments_qs, many=True).data
        combos = ComboSerializer(combos_qs, many=True).data
        journeys = JourneySerializer(journeys_qs, many=True).data
        categories = CategorySerializer(categories_qs, many=True).data
        zones = ZoneSerializer(zones_qs, many=True).data
        techniques = TechniqueSerializer(techniques_qs, many=True).data
        objectives = ObjectiveSerializer(objectives_qs, many=True).data
        intensities = IntensitySerializer(intensities_qs, many=True).data

        return Response(
            {
                "treatments": treatments,
                "combos": combos,
                "journeys": journeys,
                "categories": categories,
                "zones": zones,
                "filters": {
                    "techniques": techniques,
                    "objectives": objectives,
                    "intensities": intensities,
                },
            }
        )

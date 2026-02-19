from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from apps.catalog.models import *
from apps.catalog.serializers import (
    TreatmentSerializer,
    ComboSerializer,
    JourneySerializer,
    CategorySerializer,
    ZoneSerializer,
)


class CatalogSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        treatments_qs = Treatment.objects.all().prefetch_related("media", "tags")
        combos_qs = Combo.objects.all().prefetch_related("media", "tags")
        journeys_qs = Journey.objects.all().prefetch_related("media")
        categories_qs = Category.objects.all()
        zones_qs = Zone.objects.all()

        treatments = TreatmentSerializer(treatments_qs, many=True).data
        combos = ComboSerializer(combos_qs, many=True).data
        journeys = JourneySerializer(journeys_qs, many=True).data
        categories = CategorySerializer(categories_qs, many=True).data
        zones = ZoneSerializer(zones_qs, many=True).data

        return Response(
            {
                "treatments": treatments,
                "combos": combos,
                "journeys": journeys,
                "categories": categories,
                "zones": zones,
            }
        )

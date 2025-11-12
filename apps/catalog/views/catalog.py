from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from apps.catalog.models import *
from apps.catalog.serializers.treatment import TreatmentSerializer
from apps.catalog.serializers.combo import ComboSerializer
from apps.catalog.serializers.journey import JourneySerializer
from apps.catalog.serializers.filters import (
    CategorySerializer,
    ZoneSerializer,
    TreatmentTypeSerializer,
    ObjectiveSerializer,
    IntensityLevelSerializer,
    DurationBucketSerializer,
)


class CatalogSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        treatments = TreatmentSerializer(Treatment.objects.all(), many=True).data
        combos = ComboSerializer(Combo.objects.all(), many=True).data
        journeys = JourneySerializer(Journey.objects.all(), many=True).data
        categories = CategorySerializer(Category.objects.all(), many=True).data

        filters = {
            "kinds": {
                "title": "Clase de Tratamiento",
                "options": [
                    {"id": "treatment", "name": "Tratamientos"},
                    {"id": "combo", "name": "Combos"},
                    {"id": "journey", "name": "Jornadas"},
                ],
                "filterType": "scalar",
                "field": "kind",
            },
            "categories": {
                "title": "Categoría",
                "options": categories,
                "filterType": "scalar",
                "field": "category",
            },
            "zones": {
                "title": "Zona del Cuerpo",
                "options": ZoneSerializer(Zone.objects.all(), many=True).data,
                "filterType": "array",
                "field": "zoneIds",
                "mode": "any",
            },
            "treatmentTypes": {
                "title": "Tipo de Tratamiento",
                "options": TreatmentTypeSerializer(
                    TreatmentType.objects.all(), many=True
                ).data,
                "filterType": "array",
                "field": "treatmentTypeIds",
                "mode": "any",
            },
            "objectives": {
                "title": "Objetivos",
                "options": ObjectiveSerializer(Objective.objects.all(), many=True).data,
                "filterType": "array",
                "field": "objectiveIds",
                "mode": "any",
            },
            "durations": {
                "title": "Duración",
                "options": DurationBucketSerializer(
                    DurationBucket.objects.all(), many=True
                ).data,
                "filterType": "array",
                "field": "durationBucketIds",
                "mode": "any",
            },
            "intensities": {
                "title": "Intensidad",
                "options": IntensityLevelSerializer(
                    IntensityLevel.objects.all(), many=True
                ).data,
                "filterType": "array",
                "field": "intensityIds",
                "mode": "any",
            },
            "priceRange": {
                "title": "Rango de Precio",
                "options": [5000, 100000],  # configurable
                "filterType": "range",
                "field": "currentPrice",
                "step": 5000,
            },
            "journey": {
                "title": "Jornada",
                "options": journeys,
                "filterType": "scalar",
                "field": "journey",
            },
        }

        return Response(
            {
                "treatments": treatments + combos + journeys,
                "categories": categories,
                "filters": filters,
            }
        )

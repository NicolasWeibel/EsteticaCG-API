from typing import Optional, Dict, Any

from django.db.models import Min, Max
from django.db.models.functions import Coalesce

from ..models import (
    Category,
    Journey,
    Objective,
    Zone,
    Technique,
    Intensity,
    TreatmentZoneConfig,
    Combo,
)
from ..serializers import (
    ObjectiveSerializer,
    ZoneSerializer,
    TechniqueSerializer,
    IntensitySerializer,
)


def _min_value(*values):
    vals = [v for v in values if v is not None]
    return min(vals) if vals else None


def _max_value(*values):
    vals = [v for v in values if v is not None]
    return max(vals) if vals else None


def build_filters_summary(
    *,
    category: Optional[Category] = None,
    journey: Optional[Journey] = None,
) -> Dict[str, Any]:
    if journey and not category:
        category = journey.category

    if category is None:
        return {}

    objectives_qs = Objective.objects.filter(category=category)
    zones_qs = Zone.objects.filter(category=category)
    techniques_qs = Technique.objects.filter(category=category)
    intensities_qs = Intensity.objects.filter(category=category)
    journeys_qs = Journey.objects.filter(category=category)

    if journey:
        tzc_qs = TreatmentZoneConfig.objects.filter(
            treatment__journey=journey,
            treatment__is_active=True,
        )
        combos_qs = Combo.objects.filter(journey=journey, is_active=True)
    else:
        tzc_qs = TreatmentZoneConfig.objects.filter(
            treatment__category=category,
            treatment__is_active=True,
        )
        combos_qs = Combo.objects.filter(category=category, is_active=True)

    tzc_aggs = tzc_qs.aggregate(
        min_price=Min(Coalesce("promotional_price", "price")),
        max_price=Max(Coalesce("promotional_price", "price")),
        min_duration=Min("duration"),
        max_duration=Max("duration"),
    )
    combo_aggs = combos_qs.aggregate(
        min_price=Min(Coalesce("promotional_price", "price")),
        max_price=Max(Coalesce("promotional_price", "price")),
        min_duration=Min("duration"),
        max_duration=Max("duration"),
    )

    price_min = _min_value(tzc_aggs["min_price"], combo_aggs["min_price"])
    price_max = _max_value(tzc_aggs["max_price"], combo_aggs["max_price"])
    duration_min = _min_value(tzc_aggs["min_duration"], combo_aggs["min_duration"])
    duration_max = _max_value(tzc_aggs["max_duration"], combo_aggs["max_duration"])

    return {
        "kinds": {
            "title": "Clase de Tratamiento",
            "filter_type": "scalar",
            "field": "kind",
            "options": [
                {"id": "treatment", "name": "Tratamientos"},
                {"id": "combo", "name": "Combos"},
                {"id": "journey", "name": "Jornadas"},
            ],
        },
        "zones": {
            "title": "Zona del Cuerpo",
            "filter_type": "array",
            "field": "zone_ids",
            "mode": "any",
            "options": ZoneSerializer(zones_qs, many=True).data,
        },
        "techniques": {
            "title": "Tipo de Técnica",
            "filter_type": "array",
            "field": "technique_ids",
            "mode": "any",
            "options": TechniqueSerializer(techniques_qs, many=True).data,
        },
        "objectives": {
            "title": "Objetivos",
            "filter_type": "array",
            "field": "objective_ids",
            "mode": "any",
            "options": ObjectiveSerializer(objectives_qs, many=True).data,
        },
        "intensities": {
            "title": "Intensidad",
            "filter_type": "array",
            "field": "intensity_ids",
            "mode": "any",
            "options": IntensitySerializer(intensities_qs, many=True).data,
        },
        "durations": {
            "title": "Duración",
            "filter_type": "range",
            "field": "duration",
            "options": {"min": duration_min, "max": duration_max},
        },
        "price_range": {
            "title": "Rango de Precio",
            "filter_type": "range",
            "field": "current_price",
            "options": {"min": price_min, "max": price_max},
        },
        "journey": {
            "title": "Jornada",
            "filter_type": "scalar",
            "field": "journey_id",
            "options": list(journeys_qs.values("id", "title", "slug")),
        },
    }

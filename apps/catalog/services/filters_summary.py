from typing import Optional, Dict, Any

from django.db.models import Min, Max
from django.db.models.functions import Coalesce

from ..models import (
    Category,
    Journey,
    Objective,
    Zone,
    TreatmentType,
    IntensityLevel,
    TreatmentZoneConfig,
    Combo,
)
from ..serializers import (
    ObjectiveSerializer,
    ZoneSerializer,
    TreatmentTypeSerializer,
    IntensityLevelSerializer,
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
        return {
            "objectives": [],
            "zones": [],
            "treatment_types": [],
            "intensities": [],
            "journeys": [],
            "durations": {"min": None, "max": None},
            "prices": {"min": None, "max": None},
        }

    objectives_qs = Objective.objects.filter(category=category)
    zones_qs = Zone.objects.filter(category=category)
    treatment_types_qs = TreatmentType.objects.all()
    intensities_qs = IntensityLevel.objects.all()
    journeys_qs = Journey.objects.filter(category=category)

    if journey:
        tzc_qs = TreatmentZoneConfig.objects.filter(treatment__journey=journey)
        combos_qs = Combo.objects.filter(journey=journey)
    else:
        tzc_qs = TreatmentZoneConfig.objects.filter(treatment__category=category)
        combos_qs = Combo.objects.filter(category=category)

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
        "objectives": ObjectiveSerializer(objectives_qs, many=True).data,
        "zones": ZoneSerializer(zones_qs, many=True).data,
        "treatment_types": TreatmentTypeSerializer(treatment_types_qs, many=True).data,
        "intensities": IntensityLevelSerializer(intensities_qs, many=True).data,
        "journeys": list(journeys_qs.values("id", "title", "slug")),
        "durations": {"min": duration_min, "max": duration_max},
        "prices": {"min": price_min, "max": price_max},
    }

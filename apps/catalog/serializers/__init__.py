# =========================================
# apps/catalog/serializers/__init__.py
# Aggregator limpio para usar: from apps.catalog.serializers import X
# =========================================
from .base import UUIDSerializer
from .category import CategorySerializer
from .zone import ZoneSerializer
from .treatmentzoneconfig import TreatmentZoneConfigSerializer
from .treatment import TreatmentSerializer
from .journey import JourneySerializer
from .incompatibility import TreatmentZoneIncompatibilitySerializer
from .gallery import (
    TreatmentImageSerializer,
    ComboImageSerializer,
    JourneyImageSerializer,
)
from .combo import (
    ComboIngredientSerializer,
    ComboStepItemSerializer,
    ComboStepSerializer,
    ComboSerializer,
)
from .filters import (
    TreatmentTypeSerializer,
    ObjectiveSerializer,
    IntensityLevelSerializer,
    DurationBucketSerializer,
    TagSerializer,
)

__all__ = [
    # base
    "UUIDSerializer",
    # catalog
    "CategorySerializer",
    "ZoneSerializer",
    "TreatmentZoneConfigSerializer",
    "TreatmentSerializer",
    "TreatmentImageSerializer",
    "JourneySerializer",
    "JourneyImageSerializer",
    "TreatmentZoneIncompatibilitySerializer",
    # combo
    "ComboIngredientSerializer",
    "ComboStepItemSerializer",
    "ComboStepSerializer",
    "ComboSerializer",
    "ComboImageSerializer",
    # filters
    "TreatmentTypeSerializer",
    "ObjectiveSerializer",
    "IntensityLevelSerializer",
    "DurationBucketSerializer",
    "TagSerializer",
]

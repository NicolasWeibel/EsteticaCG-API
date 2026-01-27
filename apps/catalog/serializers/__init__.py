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
from .item_content import (
    ItemBenefitSerializer,
    ItemRecommendedPointSerializer,
    ItemFAQSerializer,
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
    TagSerializer,
)
from .ordering import ItemOrderSerializer
from .placement import PlacementSerializer, PlacementItemSerializer

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
    "ItemBenefitSerializer",
    "ItemRecommendedPointSerializer",
    "ItemFAQSerializer",
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
    "TagSerializer",
    "ItemOrderSerializer",
    "PlacementSerializer",
    "PlacementItemSerializer",
]

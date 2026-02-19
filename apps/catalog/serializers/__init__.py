# =========================================
# apps/catalog/serializers/__init__.py
# Aggregator limpio para usar: from apps.catalog.serializers import X
# =========================================
from .base import UUIDSerializer
from .category import CategorySerializer
from .zone import ZoneSerializer
from .treatmentzoneconfig import TreatmentZoneConfigSerializer
from .treatment import TreatmentSerializer, PublicTreatmentSerializer
from .journey import JourneySerializer, PublicJourneySerializer
from .incompatibility import TreatmentZoneIncompatibilitySerializer
from .gallery import (
    TreatmentMediaSerializer,
    ComboMediaSerializer,
    JourneyMediaSerializer,
)
from .item_content import (
    ItemBenefitSerializer,
    ItemRecommendedPointSerializer,
    ItemFAQSerializer,
)
from .combo import (
    ComboIngredientSerializer,
    ComboSessionItemSerializer,
    ComboSerializer,
    PublicComboSerializer,
)
from .filters import (
    TechniqueSerializer,
    ObjectiveSerializer,
    IntensitySerializer,
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
    "PublicTreatmentSerializer",
    "TreatmentMediaSerializer",
    "JourneySerializer",
    "PublicJourneySerializer",
    "JourneyMediaSerializer",
    "TreatmentZoneIncompatibilitySerializer",
    "ItemBenefitSerializer",
    "ItemRecommendedPointSerializer",
    "ItemFAQSerializer",
    # combo
    "ComboIngredientSerializer",
    "ComboSessionItemSerializer",
    "ComboSerializer",
    "PublicComboSerializer",
    "ComboMediaSerializer",
    # filters
    "TechniqueSerializer",
    "ObjectiveSerializer",
    "IntensitySerializer",
    "TagSerializer",
    "ItemOrderSerializer",
    "PlacementSerializer",
    "PlacementItemSerializer",
]

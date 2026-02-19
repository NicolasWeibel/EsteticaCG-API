from ..models import (
    Technique,
    Objective,
    Intensity,
    Tag,
)
from .base import UUIDSerializer


class TechniqueSerializer(UUIDSerializer):
    class Meta:
        model = Technique
        fields = "__all__"


class ObjectiveSerializer(UUIDSerializer):
    class Meta:
        model = Objective
        fields = "__all__"


class IntensitySerializer(UUIDSerializer):
    class Meta:
        model = Intensity
        fields = "__all__"


class TagSerializer(UUIDSerializer):
    class Meta:
        model = Tag
        fields = "__all__"

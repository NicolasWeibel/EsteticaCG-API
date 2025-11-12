from ..models import (
    TreatmentType,
    Objective,
    IntensityLevel,
    DurationBucket,
)
from .base import UUIDSerializer


class TreatmentTypeSerializer(UUIDSerializer):
    class Meta:
        model = TreatmentType
        fields = "__all__"


class ObjectiveSerializer(UUIDSerializer):
    class Meta:
        model = Objective
        fields = "__all__"


class IntensityLevelSerializer(UUIDSerializer):
    class Meta:
        model = IntensityLevel
        fields = "__all__"


class DurationBucketSerializer(UUIDSerializer):
    class Meta:
        model = DurationBucket
        fields = "__all__"

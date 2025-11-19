from rest_framework import viewsets
from ..models import TreatmentType, Objective, IntensityLevel, DurationBucket
from ..serializers import (
    TreatmentTypeSerializer,
    ObjectiveSerializer,
    IntensityLevelSerializer,
    DurationBucketSerializer,
)
from ..permissions import IsAdminOrReadOnly


class TreatmentTypeViewSet(viewsets.ModelViewSet):
    queryset = TreatmentType.objects.all()
    serializer_class = TreatmentTypeSerializer
    permission_classes = [IsAdminOrReadOnly]


class ObjectiveViewSet(viewsets.ModelViewSet):
    queryset = Objective.objects.all()
    serializer_class = ObjectiveSerializer
    permission_classes = [IsAdminOrReadOnly]


class IntensityLevelViewSet(viewsets.ModelViewSet):
    queryset = IntensityLevel.objects.all()
    serializer_class = IntensityLevelSerializer
    permission_classes = [IsAdminOrReadOnly]


class DurationBucketViewSet(viewsets.ModelViewSet):
    queryset = DurationBucket.objects.all()
    serializer_class = DurationBucketSerializer
    permission_classes = [IsAdminOrReadOnly]

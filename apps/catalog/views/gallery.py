from rest_framework import mixins, viewsets

from ..models import TreatmentImage, ComboImage, JourneyImage
from ..permissions import IsAdminOrReadOnly
from ..serializers import (
    TreatmentImageSerializer,
    ComboImageSerializer,
    JourneyImageSerializer,
)


class TreatmentImageViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = TreatmentImage.objects.all()
    serializer_class = TreatmentImageSerializer
    permission_classes = [IsAdminOrReadOnly]


class ComboImageViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = ComboImage.objects.all()
    serializer_class = ComboImageSerializer
    permission_classes = [IsAdminOrReadOnly]


class JourneyImageViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = JourneyImage.objects.all()
    serializer_class = JourneyImageSerializer
    permission_classes = [IsAdminOrReadOnly]

from rest_framework import mixins, viewsets

from ..models import TreatmentMedia, ComboMedia, JourneyMedia
from ..permissions import IsAdminOrReadOnly
from ..serializers import (
    TreatmentMediaSerializer,
    ComboMediaSerializer,
    JourneyMediaSerializer,
)


class TreatmentMediaViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = TreatmentMedia.objects.all()
    serializer_class = TreatmentMediaSerializer
    permission_classes = [IsAdminOrReadOnly]


class ComboMediaViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = ComboMedia.objects.all()
    serializer_class = ComboMediaSerializer
    permission_classes = [IsAdminOrReadOnly]


class JourneyMediaViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = JourneyMedia.objects.all()
    serializer_class = JourneyMediaSerializer
    permission_classes = [IsAdminOrReadOnly]

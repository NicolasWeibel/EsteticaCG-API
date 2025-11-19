from rest_framework import viewsets
from ..models import Journey
from ..serializers import JourneySerializer
from ..permissions import IsAdminOrReadOnly


class JourneyViewSet(viewsets.ModelViewSet):
    queryset = Journey.objects.all().order_by("title")
    serializer_class = JourneySerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["category"]

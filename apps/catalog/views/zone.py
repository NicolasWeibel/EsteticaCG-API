from rest_framework import viewsets
from ..models import Zone
from ..serializers import ZoneSerializer
from ..permissions import IsAdminOrReadOnly


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all().order_by("name")
    serializer_class = ZoneSerializer
    permission_classes = [IsAdminOrReadOnly]

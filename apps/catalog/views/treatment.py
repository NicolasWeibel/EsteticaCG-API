from rest_framework import viewsets
from ..permissions import IsAdminOrReadOnly
from ..models import Treatment
from ..serializers.treatment import TreatmentSerializer


class TreatmentViewSet(viewsets.ModelViewSet):
    queryset = Treatment.objects.all().order_by("-title")
    serializer_class = TreatmentSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["category", "journey"]
    search_fields = ["title", "description"]

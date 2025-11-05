from rest_framework import viewsets, permissions
from ...models import Treatment
from .serializers import TreatmentSerializer


class TreatmentViewSet(viewsets.ModelViewSet):
    queryset = Treatment.objects.all().order_by("-updated_at")
    serializer_class = TreatmentSerializer
    permission_classes = [permissions.IsAuthenticated]  # usa JWT luego
    filterset_fields = ["is_active", "is_featured"]
    search_fields = ["name", "description"]
    ordering_fields = ["updated_at", "name"]

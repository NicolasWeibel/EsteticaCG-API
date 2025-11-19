from rest_framework import viewsets
from ..models import Combo
from ..serializers import ComboSerializer
from ..permissions import IsAdminOrReadOnly


class ComboViewSet(viewsets.ModelViewSet):
    queryset = Combo.objects.all().order_by("-title")
    serializer_class = ComboSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["category", "journey"]
    search_fields = ["title", "description"]

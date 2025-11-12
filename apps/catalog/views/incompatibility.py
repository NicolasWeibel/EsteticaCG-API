from rest_framework import viewsets
from ..models import TreatmentZoneIncompatibility
from ..serializers.incompatibility import TreatmentZoneIncompatibilitySerializer
from ..permissions import IsAdminOnly


class TreatmentZoneIncompatibilityViewSet(viewsets.ModelViewSet):
    queryset = TreatmentZoneIncompatibility.objects.all()
    serializer_class = TreatmentZoneIncompatibilitySerializer
    permission_classes = [IsAdminOnly]

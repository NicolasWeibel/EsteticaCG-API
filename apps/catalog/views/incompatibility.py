from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.response import Response

from ..models import TreatmentZoneIncompatibility
from ..permissions import IsAdminOnly
from ..serializers import TreatmentZoneIncompatibilitySerializer


class TreatmentZoneIncompatibilityFilter(filters.FilterSet):
    tzc = filters.UUIDFilter(method="filter_tzc")

    class Meta:
        model = TreatmentZoneIncompatibility
        fields = ["tzc", "left_tzc", "right_tzc"]

    def filter_tzc(self, queryset, name, value):
        return queryset.filter(Q(left_tzc=value) | Q(right_tzc=value))


class TreatmentZoneIncompatibilityViewSet(viewsets.ModelViewSet):
    queryset = TreatmentZoneIncompatibility.objects.all()
    serializer_class = TreatmentZoneIncompatibilitySerializer
    permission_classes = [IsAdminOnly]
    filterset_class = TreatmentZoneIncompatibilityFilter

    def list(self, request, *args, **kwargs):
        # Respuesta compacta cuando se consulta con ?tzc=<uuid>:
        # solo devuelve los otros TZC incompatibles, sin repetir el propio.
        tzc_id = request.query_params.get("tzc")
        if not tzc_id:
            return super().list(request, *args, **kwargs)

        qs = self.filter_queryset(self.get_queryset())
        other_ids = []
        for obj in qs:
            if str(obj.left_tzc_id) == tzc_id:
                other = obj.right_tzc_id
            else:
                other = obj.left_tzc_id
            if other and other not in other_ids:
                other_ids.append(other)

        return Response(other_ids)

from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import TreatmentType, Objective, IntensityLevel, Tag, Category, Journey
from ..serializers import (
    TreatmentTypeSerializer,
    ObjectiveSerializer,
    IntensityLevelSerializer,
    TagSerializer,
)
from ..permissions import IsAdminOrReadOnly
from ..services.filters_summary import build_filters_summary


class TreatmentTypeViewSet(viewsets.ModelViewSet):
    queryset = TreatmentType.objects.all()
    serializer_class = TreatmentTypeSerializer
    permission_classes = [IsAdminOrReadOnly]


class ObjectiveViewSet(viewsets.ModelViewSet):
    queryset = Objective.objects.all()
    serializer_class = ObjectiveSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        category_id = self.request.query_params.get("category")
        if category_id:
            qs = qs.filter(category_id=category_id)
        return qs


class IntensityLevelViewSet(viewsets.ModelViewSet):
    queryset = IntensityLevel.objects.all()
    serializer_class = IntensityLevelSerializer
    permission_classes = [IsAdminOrReadOnly]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ["name"]


class FiltersSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        category_id = request.query_params.get("category")
        journey_id = request.query_params.get("journey")
        category = None
        journey = None

        if category_id:
            category = Category.objects.filter(id=category_id).first()
        if journey_id:
            journey = Journey.objects.filter(id=journey_id).first()
            if journey and not category:
                category = journey.category

        summary = build_filters_summary(category=category, journey=journey)
        return Response({"filters": summary})

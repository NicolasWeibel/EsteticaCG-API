from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PublicReviewsQuerySerializer
from .services import get_public_reviews


class PublicReviewsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = PublicReviewsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        payload = get_public_reviews(
            provider=query.validated_data.get("provider", settings.REVIEWS_PROVIDER),
            min_rating=query.validated_data.get(
                "min_rating", settings.REVIEWS_DEFAULT_MIN_RATING
            ),
            with_content=query.validated_data.get(
                "with_content", settings.REVIEWS_DEFAULT_WITH_CONTENT
            ),
            limit=query.validated_data.get("limit", settings.REVIEWS_PUBLIC_LIMIT),
        )
        return Response(payload)

from rest_framework import serializers


class PublicReviewsQuerySerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        choices=("manual", "google"),
        required=False,
    )
    min_rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    with_content = serializers.BooleanField(required=False)
    limit = serializers.IntegerField(min_value=1, max_value=50, required=False)

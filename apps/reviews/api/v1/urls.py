from django.urls import path

from ...views import PublicReviewsView

app_name = "reviews"

urlpatterns = [
    path("", PublicReviewsView.as_view(), name="public-reviews"),
]

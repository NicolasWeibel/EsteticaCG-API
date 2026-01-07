# ===========================================
# apps/users/api/v1/urls.py
# ===========================================
from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import (
    SessionToJWTView,
    LogoutView,
    MeView,
    ProfileView,
    RequestDniChangeCodeView,
    RequestDniClaimCodeView,
    GoogleLoginStartView,
    GoogleLoginCompleteView,
    ClientViewSet,
)

app_name = "users_api_v1"
router = SimpleRouter()
router.register(r"clients", ClientViewSet, basename="client")
urlpatterns = [
    path("session-to-jwt/", SessionToJWTView.as_view(), name="session-to-jwt"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path(
        "profile/request-dni-change/",
        RequestDniChangeCodeView.as_view(),
        name="profile-request-dni-change",
    ),
    path(
        "profile/request-dni-claim/",
        RequestDniClaimCodeView.as_view(),
        name="profile-request-dni-claim",
    ),
    path("google/login/", GoogleLoginStartView.as_view(), name="google-start"),
    path("google/callback/", GoogleLoginCompleteView.as_view(), name="google-complete"),
]
urlpatterns += router.urls

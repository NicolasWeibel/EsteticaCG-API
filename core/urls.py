from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Google (crea sesión)
    path("accounts/", include("allauth.urls")),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema")),
    # API v1
    path(
        "api/v1/catalog/",
        include(("apps.catalog.api.v1.urls", "catalog"), namespace="catalog"),
    ),
    path(
        "api/v1/auth/",
        include(("apps.authcodes.api.v1.urls", "authcodes"), namespace="authcodes"),
    ),  # OTP
    path(
        "api/v1/auth/",
        include(("apps.users.api.v1.urls", "users_api_v1"), namespace="users_api_v1"),
    ),  # Google→JWT + me/logout
    # JWT helpers
    path("api/v1/auth/jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
    path("api/v1/auth/jwt/verify/", TokenVerifyView.as_view(), name="jwt-verify"),
]

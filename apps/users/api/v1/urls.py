# ===========================================
# apps/users/api/v1/urls.py
# ===========================================
from django.urls import path
from .views import SessionToJWTView, LogoutView, MeView, google_login_start

app_name = "users_api_v1"
urlpatterns = [
    path("session-to-jwt/", SessionToJWTView.as_view(), name="session-to-jwt"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("google/login/", google_login_start, name="google-login"),
]

# apps/authcodes/api/v1/urls.py
from django.urls import path
from apps.authcodes.views import RequestCodeView, VerifyCodeView

app_name = "auth"  # why: permite reverse("auth:request-code")
urlpatterns = [
    path("request-code/", RequestCodeView.as_view(), name="request-code"),
    path("verify-code/", VerifyCodeView.as_view(), name="verify-code"),
]

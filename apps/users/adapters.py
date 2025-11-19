# ===========================================
# apps/users/adapters.py
# (asegúrate de tener este archivo si usas SOCIALACCOUNT_ADAPTER)
# ===========================================
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class SocialOnlySignupAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        # Por qué: permitir alta por social aunque ACCOUNT_SIGNUP_ENABLED=False
        return True

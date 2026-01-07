from allauth.socialaccount.signals import social_account_added, social_account_updated
from django.dispatch import receiver

from apps.users.services import ensure_client_for_user


def _extract_google_data(sociallogin):
    data = sociallogin.account.extra_data or {}
    return (
        data.get("given_name"),
        data.get("family_name"),
        data.get("picture"),
    )


@receiver(social_account_added)
def handle_social_account_added(request, sociallogin, **kwargs):
    if sociallogin.account.provider != "google":
        return
    first_name, last_name, avatar_url = _extract_google_data(sociallogin)
    ensure_client_for_user(
        user=sociallogin.user,
        email=sociallogin.user.email,
        first_name=first_name,
        last_name=last_name,
        google_avatar_url=avatar_url,
    )


@receiver(social_account_updated)
def handle_social_account_updated(request, sociallogin, **kwargs):
    if sociallogin.account.provider != "google":
        return
    first_name, last_name, avatar_url = _extract_google_data(sociallogin)
    ensure_client_for_user(
        user=sociallogin.user,
        email=sociallogin.user.email,
        first_name=first_name,
        last_name=last_name,
        google_avatar_url=avatar_url,
    )

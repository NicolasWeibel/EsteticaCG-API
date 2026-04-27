from allauth.socialaccount.signals import social_account_added, social_account_updated
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.shared.cloudinary import delete_uploaded_asset
from apps.users.models import Client
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
        sync_google_profile_name=True,
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
        sync_google_profile_name=True,
    )


def _delete_cloudinary_avatar(file_field):
    if not file_field:
        return
    try:
        delete_uploaded_asset(file_field.name, resource_type="image")
    except Exception:
        pass


@receiver(pre_save, sender=Client)
def capture_old_custom_avatar(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = Client.objects.get(pk=instance.pk)
    except Client.DoesNotExist:
        return
    old_avatar = getattr(old_instance, "custom_avatar", None)
    new_avatar = getattr(instance, "custom_avatar", None)
    if old_avatar and old_avatar != new_avatar:
        instance._old_custom_avatar_to_cleanup = old_avatar


@receiver(post_save, sender=Client)
def cleanup_old_custom_avatar(sender, instance, **kwargs):
    old_avatar = getattr(instance, "_old_custom_avatar_to_cleanup", None)
    if not old_avatar:
        return
    _delete_cloudinary_avatar(old_avatar)
    delattr(instance, "_old_custom_avatar_to_cleanup")


@receiver(post_delete, sender=Client)
def cleanup_custom_avatar_on_delete(sender, instance, **kwargs):
    _delete_cloudinary_avatar(instance.custom_avatar)

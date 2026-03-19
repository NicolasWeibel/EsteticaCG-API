import pytest
from django.contrib.auth import get_user_model

from apps.users.models import Client
from apps.users.services import ensure_client_for_user, update_client_profile


@pytest.mark.django_db
def test_google_login_updates_avatar_but_keeps_manual_name_changes():
    User = get_user_model()
    user = User.objects.create_user(email="cliente@example.com")

    client = ensure_client_for_user(
        user=user,
        email=user.email,
        first_name="Ana",
        last_name="Google",
        google_avatar_url="https://google.example/avatar-1.jpg",
        sync_google_profile_name=True,
    )

    assert client.first_name == "Ana"
    assert client.last_name == "Google"
    assert client.google_avatar_url == "https://google.example/avatar-1.jpg"
    assert client.google_profile_sync_enabled is True

    client = update_client_profile(
        user=user,
        data={"first_name": "Anita", "last_name": "Perez"},
    )

    assert client.first_name == "Anita"
    assert client.last_name == "Perez"
    assert client.google_profile_sync_enabled is False

    client = ensure_client_for_user(
        user=user,
        email=user.email,
        first_name="Ana Maria",
        last_name="Google Nueva",
        google_avatar_url="https://google.example/avatar-2.jpg",
        sync_google_profile_name=True,
    )

    assert client.first_name == "Anita"
    assert client.last_name == "Perez"
    assert client.google_avatar_url == "https://google.example/avatar-2.jpg"


@pytest.mark.django_db
def test_google_login_keeps_syncing_names_until_user_edits_them():
    User = get_user_model()
    user = User.objects.create_user(email="nuevo@example.com")

    client = ensure_client_for_user(
        user=user,
        email=user.email,
        first_name="Luz",
        last_name="Original",
        google_avatar_url="https://google.example/avatar-1.jpg",
        sync_google_profile_name=True,
    )

    client = ensure_client_for_user(
        user=user,
        email=user.email,
        first_name="Luz Maria",
        last_name="Actualizada",
        google_avatar_url="https://google.example/avatar-2.jpg",
        sync_google_profile_name=True,
    )

    assert client.first_name == "Luz Maria"
    assert client.last_name == "Actualizada"
    assert client.google_avatar_url == "https://google.example/avatar-2.jpg"
    assert client.google_profile_sync_enabled is True


@pytest.mark.django_db
def test_google_login_does_not_override_existing_local_client_names():
    User = get_user_model()
    user = User.objects.create_user(email="reserva@example.com")
    Client.objects.create(
        email=user.email,
        first_name="Nombre Local",
        last_name="Apellido Local",
    )

    client = ensure_client_for_user(
        user=user,
        email=user.email,
        first_name="Google Name",
        last_name="Google Lastname",
        google_avatar_url="https://google.example/avatar-1.jpg",
        sync_google_profile_name=True,
    )

    assert client.first_name == "Nombre Local"
    assert client.last_name == "Apellido Local"
    assert client.google_avatar_url == "https://google.example/avatar-1.jpg"
    assert client.google_profile_sync_enabled is False

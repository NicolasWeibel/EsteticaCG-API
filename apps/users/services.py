from django.db import transaction
from apps.users.models import Client
from apps.authcodes.models import OTPLoginCode


MSG_DNI_HAS_ACCOUNT = "Este DNI ya tiene cuenta. Inicia sesion para continuar."
MSG_EMAIL_HAS_ACCOUNT = "Ese email ya esta asociado a una cuenta. Inicia sesion para continuar."
MSG_DNI_IN_USE = "Este DNI ya esta asociado a otra cuenta."
MSG_EMAIL_DNI_MISMATCH = "Ese email ya esta asociado a otro DNI. Revisa los datos."
MSG_DNI_EMAIL_MISMATCH = "Este DNI ya esta asociado a otro email. Revisa los datos."
MSG_DNI_VERIFY_REQUIRED = "Necesitas verificar este DNI para continuar."
MSG_DNI_CHANGE_VERIFY_REQUIRED = "Necesitas verificar el cambio de DNI."
MSG_VERIFICATION_INVALID = "Codigo de verificacion invalido o expirado."


class ClientMatchError(Exception):
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _clean_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    return value


def _apply_updates(client: Client, clearable_fields=None, **data) -> bool:
    changed = False
    clearable = set(clearable_fields or [])
    for field, value in data.items():
        if field in clearable and value is None:
            if getattr(client, field) is not None:
                setattr(client, field, None)
                changed = True
            continue
        cleaned = _clean_value(value)
        if cleaned is None:
            continue
        if getattr(client, field) != cleaned:
            setattr(client, field, cleaned)
            changed = True
    if changed:
        client.save()
    return changed


def _verify_code_or_raise(*, email: str, raw_code: str | None, purpose: str, message: str):
    if not raw_code:
        raise ClientMatchError(message)
    verified = OTPLoginCode.verify_latest(
        email=email, raw_code=raw_code, purpose=purpose
    )
    if not verified:
        raise ClientMatchError(MSG_VERIFICATION_INVALID)


def _attach_user_to_client(*, user, current: Client, target: Client) -> Client:
    if current.pk != target.pk:
        current.user = None
        current.save(update_fields=["user"])
        if _is_placeholder_client(current):
            current.delete()
    target.user = user
    target.save(update_fields=["user"])
    return target


def _is_placeholder_client(client: Client) -> bool:
    if client.bookings_count:
        return False
    if client.last_booking_date:
        return False
    if client.notes:
        return False
    if client.dni:
        return False
    if client.first_name or client.last_name:
        return False
    if client.gender:
        return False
    if client.phone_number:
        return False
    if client.google_avatar_url:
        return False
    if client.custom_avatar:
        return False
    if client.birth_date:
        return False
    return True


@transaction.atomic
def smart_match_client(
    *,
    email: str,
    dni: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    gender: str | None = None,
    phone_number: str | None = None,
):
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise ValueError("email is required")

    cleaned_dni = _clean_value(dni)
    if not cleaned_dni:
        raise ValueError("dni is required")

    account_by_dni = (
        Client.objects.select_for_update()
        .filter(dni=cleaned_dni, user__isnull=False)
        .first()
    )
    if account_by_dni:
        raise ClientMatchError(MSG_DNI_HAS_ACCOUNT)

    account_by_email = (
        Client.objects.select_for_update()
        .filter(email__iexact=normalized_email, user__isnull=False)
        .first()
    )
    if account_by_email:
        raise ClientMatchError(MSG_EMAIL_HAS_ACCOUNT)

    client = (
        Client.objects.select_for_update()
        .filter(dni=cleaned_dni, user__isnull=True)
        .first()
    )
    if client:
        if client.email and normalize_email(client.email) != normalized_email:
            raise ClientMatchError(MSG_DNI_EMAIL_MISMATCH)
        _apply_updates(
            client,
            email=normalized_email,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            phone_number=phone_number,
        )
        return client, False

    client = (
        Client.objects.select_for_update()
        .filter(email__iexact=normalized_email, user__isnull=True)
        .order_by("created_at")
        .first()
    )
    if client:
        if client.dni and client.dni != cleaned_dni:
            raise ClientMatchError(MSG_EMAIL_DNI_MISMATCH)
        updates = {
            "email": normalized_email,
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": phone_number,
        }
        if not client.dni:
            updates["dni"] = cleaned_dni
        if gender and not client.gender:
            updates["gender"] = gender
        _apply_updates(client, **updates)
        return client, False

    client = Client.objects.create(
        email=normalized_email,
        dni=cleaned_dni,
        first_name=_clean_value(first_name) or "",
        last_name=_clean_value(last_name) or "",
        gender=_clean_value(gender),
        phone_number=_clean_value(phone_number) or "",
    )
    return client, True


@transaction.atomic
def ensure_client_for_user(
    *,
    user,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    google_avatar_url: str | None = None,
    sync_google_profile_name: bool = False,
):
    client = Client.objects.select_for_update().filter(user=user).first()
    normalized_email = normalize_email(email or user.email)
    google_name_updates = {"email": normalized_email, "google_avatar_url": google_avatar_url}
    should_sync_google_name = bool(
        sync_google_profile_name
        and (
            not client
            or client.google_profile_sync_enabled
            or not (client.first_name or client.last_name)
        )
    )
    if should_sync_google_name:
        google_name_updates["first_name"] = first_name
        google_name_updates["last_name"] = last_name
        google_name_updates["google_profile_sync_enabled"] = True

    if client:
        _apply_updates(client, **google_name_updates)
        return client

    guest_client = (
        Client.objects.select_for_update()
        .filter(user__isnull=True, email__iexact=normalized_email)
        .order_by("created_at")
        .first()
    )
    if guest_client:
        guest_client.user = user
        if sync_google_profile_name and (
            guest_client.google_profile_sync_enabled
            or not (guest_client.first_name or guest_client.last_name)
        ):
            google_name_updates["first_name"] = first_name
            google_name_updates["last_name"] = last_name
            google_name_updates["google_profile_sync_enabled"] = True
        else:
            google_name_updates.pop("first_name", None)
            google_name_updates.pop("last_name", None)
            google_name_updates.pop("google_profile_sync_enabled", None)
        _apply_updates(guest_client, **google_name_updates)
        guest_client.save()
        return guest_client

    return Client.objects.create(
        user=user,
        email=normalized_email,
        first_name=_clean_value(first_name) or "",
        last_name=_clean_value(last_name) or "",
        google_avatar_url=_clean_value(google_avatar_url) or "",
        google_profile_sync_enabled=sync_google_profile_name,
    )


@transaction.atomic
def update_client_profile(*, user, data: dict):
    payload = dict(data)
    verification_code = _clean_value(payload.pop("dni_verification_code", None))
    normalized_email = normalize_email(user.email)

    client = ensure_client_for_user(user=user, email=normalized_email)
    if "first_name" in payload or "last_name" in payload:
        payload["google_profile_sync_enabled"] = False
    incoming_dni = _clean_value(payload.get("dni"))
    if incoming_dni is not None:
        payload["dni"] = incoming_dni

    if incoming_dni and client.dni and incoming_dni != client.dni:
        _verify_code_or_raise(
            email=normalized_email,
            raw_code=verification_code,
            purpose=OTPLoginCode.Purpose.DNI_CHANGE,
            message=MSG_DNI_CHANGE_VERIFY_REQUIRED,
        )
        other = (
            Client.objects.select_for_update()
            .filter(dni=incoming_dni)
            .exclude(pk=client.pk)
            .first()
        )
        if other:
            raise ClientMatchError(MSG_DNI_IN_USE)
    elif incoming_dni and not client.dni:
        other = (
            Client.objects.select_for_update()
            .filter(dni=incoming_dni)
            .exclude(pk=client.pk)
            .first()
        )
        if other:
            if other.user_id:
                raise ClientMatchError(MSG_DNI_IN_USE)
            other_email = normalize_email(other.email)
            if other_email == normalized_email:
                client = _attach_user_to_client(
                    user=user, current=client, target=other
                )
            else:
                _verify_code_or_raise(
                    email=other_email,
                    raw_code=verification_code,
                    purpose=OTPLoginCode.Purpose.DNI_CLAIM,
                    message=MSG_DNI_VERIFY_REQUIRED,
                )
                client = _attach_user_to_client(
                    user=user, current=client, target=other
                )
            payload["email"] = normalized_email
        else:
            payload["email"] = normalized_email
    else:
        payload["email"] = normalized_email

    _apply_updates(
        client,
        clearable_fields={"birth_date", "custom_avatar"},
        **payload,
    )
    return client

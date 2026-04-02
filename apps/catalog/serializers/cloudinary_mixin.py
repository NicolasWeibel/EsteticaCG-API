"""Helpers for JSON-only Cloudinary media handling in serializers."""

from typing import Optional, Type

from django.db import models
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.shared.cloudinary import (
    CloudinaryAssetRef,
    CloudinaryValidationError,
    validate_cloudinary_asset,
)


class CloudinaryMediaMixin:
    """Shared helpers for JSON-only Cloudinary media payloads."""

    def _validate_cloudinary_ref(
        self,
        data,
        allowed_prefixes: list[str],
        field_name: str,
    ) -> Optional[CloudinaryAssetRef]:
        if data in ("", {}):
            return None
        if isinstance(data, str):
            data = {"public_id": data}
        try:
            return validate_cloudinary_asset(
                reference=data,
                allowed_prefixes=allowed_prefixes,
            )
        except CloudinaryValidationError as exc:
            raise ValidationError({field_name: str(exc)})

    def _pop_optional_input(self, validated_data: dict, key: str):
        if key not in validated_data:
            return serializers.empty
        return validated_data.pop(key)

    def _apply_image_input(
        self,
        instance: models.Model,
        field_name: str,
        value,
        allowed_prefixes: list[str],
    ) -> bool:
        if value is serializers.empty:
            return False
        if value in (None, "", {}):
            setattr(instance, field_name, None)
            return True
        ref = self._validate_cloudinary_ref(
            data=value,
            allowed_prefixes=allowed_prefixes,
            field_name=field_name,
        )
        if ref is None:
            setattr(instance, field_name, None)
        else:
            setattr(instance, field_name, ref.public_id)
        return True

    def _process_media_list(
        self,
        media_items: list,
        parent: models.Model,
        media_model: Type[models.Model],
        parent_field: str,
        allowed_prefixes: list[str],
    ) -> None:
        """
        Apply the complete ordered gallery list.

        Existing items omitted from `media_items` are removed.
        """
        if not isinstance(media_items, (list, tuple)):
            raise ValidationError({"media_items": "Debe ser una lista."})

        existing_qs = list(getattr(parent, "media").all())
        existing_map = {str(obj.id): obj for obj in existing_qs}
        seen_existing_ids = set()
        to_delete = []
        to_update = []
        to_create = []
        next_order = 0

        for index, item in enumerate(media_items):
            if not isinstance(item, dict):
                raise ValidationError(
                    {"media_items": f"Item en posicion {index} debe ser un objeto."}
                )

            media_id = item.get("id")
            remove = bool(item.get("remove", False))

            if media_id:
                media_id = str(media_id)
                if media_id in seen_existing_ids:
                    raise ValidationError(
                        {"media_items": f"Media duplicada en la lista: {media_id}"}
                    )
                media_obj = existing_map.get(media_id)
                if not media_obj:
                    raise ValidationError(
                        {
                            "media_items": (
                                f"La media {media_id} no pertenece a este recurso."
                            )
                        }
                    )
                seen_existing_ids.add(media_id)
                if remove:
                    to_delete.append(media_obj)
                    continue
                if media_obj.order != next_order:
                    media_obj.order = next_order
                    to_update.append(media_obj)
                next_order += 1
                continue

            public_id = item.get("public_id")
            if not public_id:
                raise ValidationError(
                    {
                        "media_items": (
                            f"Item en posicion {index} debe incluir 'id' o 'public_id'."
                        )
                    }
                )
            if not item.get("resource_type"):
                raise ValidationError(
                    {
                        "media_items": (
                            f"Item nuevo en posicion {index} debe incluir "
                            "'resource_type'."
                        )
                    }
                )
            try:
                ref = validate_cloudinary_asset(
                    reference=item,
                    allowed_prefixes=allowed_prefixes,
                )
            except CloudinaryValidationError as exc:
                raise ValidationError(
                    {"media_items": f"Media invalida en posicion {index}: {exc}"}
                )
            to_create.append(
                media_model(
                    **{parent_field: parent},
                    media=ref.public_id,
                    media_type=ref.resource_type,
                    alt_text=item.get("alt_text", ""),
                    order=next_order,
                )
            )
            next_order += 1

        for media_obj in existing_qs:
            media_id = str(media_obj.id)
            if media_id not in seen_existing_ids and media_obj not in to_delete:
                to_delete.append(media_obj)

        for obj in to_delete:
            obj.delete()

        if to_update:
            media_model.objects.bulk_update(to_update, ["order"])

        if to_create:
            media_model.objects.bulk_create(to_create)

from typing import Iterable, List

from django.db import transaction
from rest_framework.exceptions import ValidationError


def reorder_gallery(obj, ordered_ids: Iterable) -> List:
    """
    Reordena la galería de `obj` (que debe exponer `.media`).
    Incluye cualquier media no listada al final.
    """
    if not isinstance(ordered_ids, list):
        raise ValidationError("ordered_media_ids debe ser una lista")

    media_qs = getattr(obj, "media", None)
    if media_qs is None:
        raise ValidationError("El objeto no tiene galería asociada")

    ordered_set = set()
    all_media = list(media_qs.order_by("order"))
    media_map = {str(item.id): item for item in all_media}
    ordered_media = []

    try:
        with transaction.atomic():
            for img_id in ordered_ids:
                media_obj = media_map.get(str(img_id))
                if media_obj and str(media_obj.id) not in ordered_set:
                    ordered_media.append(media_obj)
                    ordered_set.add(str(media_obj.id))

            for media_obj in all_media:
                if str(media_obj.id) not in ordered_set:
                    ordered_media.append(media_obj)
                    ordered_set.add(str(media_obj.id))

            to_update = []
            for index, media_obj in enumerate(ordered_media):
                if media_obj.order != index:
                    media_obj.order = index
                    to_update.append(media_obj)

            if to_update:
                media_qs.model.objects.bulk_update(to_update, ["order"])
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(str(exc))

    return ordered_media

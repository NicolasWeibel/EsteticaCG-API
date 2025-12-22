from typing import Iterable, List

from django.db import transaction
from rest_framework.exceptions import ValidationError


def reorder_gallery(obj, ordered_ids: Iterable) -> List:
    """
    Reordena la galería de `obj` (que debe exponer `.images`).
    Incluye cualquier imagen no listada al final.
    """
    if not isinstance(ordered_ids, list):
        raise ValidationError("ordered_ids debe ser una lista")

    images_qs = getattr(obj, "images", None)
    if images_qs is None:
        raise ValidationError("El objeto no tiene galería asociada")

    ordered_set = set()
    all_images = list(images_qs.order_by("order"))
    images_map = {str(img.id): img for img in all_images}
    ordered_images = []

    try:
        with transaction.atomic():
            for img_id in ordered_ids:
                img = images_map.get(str(img_id))
                if img and str(img.id) not in ordered_set:
                    ordered_images.append(img)
                    ordered_set.add(str(img.id))

            for img in all_images:
                if str(img.id) not in ordered_set:
                    ordered_images.append(img)
                    ordered_set.add(str(img.id))

            to_update = []
            for index, img in enumerate(ordered_images):
                if img.order != index:
                    img.order = index
                    to_update.append(img)

            if to_update:
                images_qs.model.objects.bulk_update(to_update, ["order"])
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(str(exc))

    return ordered_images

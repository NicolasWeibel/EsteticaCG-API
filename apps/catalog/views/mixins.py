from django.db import transaction
from rest_framework import status
from rest_framework.response import Response


class GalleryOrderingMixin:
    """
    Helper mixin to reorder gallery images for a parent object.
    """

    image_serializer_class = None

    def _reorder_images(self, obj, ordered_ids):
        if not isinstance(ordered_ids, list):
            return Response(
                {"error": "ordered_ids debe ser una lista"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        images_qs = getattr(obj, "images", None)
        if images_qs is None:
            return Response(
                {"error": "El objeto no tiene galería asociada"},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer_cls = self.image_serializer_class
        if serializer_cls:
            ordered = images_qs.order_by("order")
            return Response(serializer_cls(ordered, many=True).data)
        return Response(status=status.HTTP_204_NO_CONTENT)

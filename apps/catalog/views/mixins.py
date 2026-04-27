from rest_framework import status
from rest_framework.response import Response

from ..utils.gallery import reorder_gallery


class GalleryOrderingMixin:
    """
    Helper mixin to reorder gallery media for a parent object.
    """

    media_serializer_class = None

    def _reorder_media(self, obj, ordered_ids):
        try:
            reorder_gallery(obj, ordered_ids)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer_cls = self.media_serializer_class
        if serializer_cls:
            ordered = obj.media.order_by("order")
            return Response(serializer_cls(ordered, many=True).data)
        return Response(status=status.HTTP_204_NO_CONTENT)

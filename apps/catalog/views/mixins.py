import json
from django.http import QueryDict
from rest_framework import status
from rest_framework.response import Response

from ..utils.gallery import reorder_gallery


class MultipartJsonMixin:
    """
    Mixin robusto para parsear campos JSON dentro de multipart/form-data.
    Convierte QueryDict a dict nativo para evitar errores con listas anidadas.
    """

    multipart_json_fields = []

    def _get_parsed_data(self, request):
        data = request.data

        # Si ya es un dict normal (JSON request), no tocamos nada
        if not isinstance(data, QueryDict):
            return data

        # 1. CONVERSIÓN SEGURA A DICT:
        # Usamos .lists() para no perder archivos múltiples (uploaded_images)
        parsed_data = {}
        for key, value in data.lists():
            # Si la lista tiene un solo elemento, lo sacamos (comportamiento estándar)
            if len(value) == 1:
                parsed_data[key] = value[0]
            else:
                parsed_data[key] = value

        # 2. PARSEO DE JSON STRINGS:
        # Campos específicos del ViewSet
        for field in self.multipart_json_fields:
            if field in parsed_data:
                val = parsed_data[field]
                if isinstance(val, str):
                    try:
                        parsed_data[field] = json.loads(val)
                    except ValueError:
                        pass

        return parsed_data

    def create(self, request, *args, **kwargs):
        parsed_data = self._get_parsed_data(request)
        serializer = self.get_serializer(data=parsed_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        parsed_data = self._get_parsed_data(request)
        serializer = self.get_serializer(instance, data=parsed_data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


class GalleryOrderingMixin:
    """
    Helper mixin to reorder gallery images for a parent object.
    """

    image_serializer_class = None

    def _reorder_images(self, obj, ordered_ids):
        try:
            reorder_gallery(obj, ordered_ids)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer_cls = self.image_serializer_class
        if serializer_cls:
            ordered = obj.images.order_by("order")
            return Response(serializer_cls(ordered, many=True).data)
        return Response(status=status.HTTP_204_NO_CONTENT)

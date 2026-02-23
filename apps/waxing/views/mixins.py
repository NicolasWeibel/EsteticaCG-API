import json

from django.http import QueryDict
from rest_framework import status
from rest_framework.response import Response


class MultipartJsonMixin:
    """
    Parsea campos JSON enviados como string dentro de multipart/form-data.
    """

    multipart_json_fields = []

    def _get_parsed_data(self, request):
        data = request.data
        if not isinstance(data, QueryDict):
            return data

        parsed_data = {}
        for key, value in data.lists():
            parsed_data[key] = value[0] if len(value) == 1 else value

        for field in self.multipart_json_fields:
            if field not in parsed_data:
                continue
            value = parsed_data[field]
            if isinstance(value, str):
                try:
                    parsed_data[field] = json.loads(value)
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
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
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

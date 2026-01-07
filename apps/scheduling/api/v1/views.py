from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.scheduling.api.v1.serializers import (
    AvailabilityBatchSerializer,
    AvailabilityBatchUpdateSerializer,
    AvailabilityCreateSerializer,
    AvailabilityDeleteQuerySerializer,
    AvailabilityListQuerySerializer,
    ScheduleBlockCreateSerializer,
    ScheduleBlockDeleteQuerySerializer,
    ScheduleBlockListQuerySerializer,
)
from apps.scheduling.models import AvailabilityBatch
from apps.scheduling.services import (
    AvailabilityConflictError,
    EmptyAvailabilityError,
    create_availability,
    create_blocks,
    delete_availability,
    delete_blocks,
    list_availability,
    list_blocks,
    update_availability_batch,
)


class AvailabilityView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        serializer = AvailabilityListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = list_availability(filters=serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AvailabilityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = create_availability(payload=serializer.validated_data)
        except AvailabilityConflictError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except EmptyAvailabilityError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)

    def delete(self, request):
        serializer = AvailabilityDeleteQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = delete_availability(filters=serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)


class ScheduleBlockView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        serializer = ScheduleBlockListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = list_blocks(filters=serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ScheduleBlockCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = create_blocks(payload=serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)

    def delete(self, request):
        serializer = ScheduleBlockDeleteQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = delete_blocks(filters=serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)


class AvailabilityBatchDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, batch_id):
        batch = AvailabilityBatch.objects.filter(id=batch_id).first()
        if not batch:
            return Response({"detail": "Batch no encontrado."}, status=404)
        return Response(AvailabilityBatchSerializer(batch).data, status=status.HTTP_200_OK)

    def patch(self, request, batch_id):
        serializer = AvailabilityBatchUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = update_availability_batch(
                batch_id=batch_id, payload=serializer.validated_data
            )
        except AvailabilityBatch.DoesNotExist:
            return Response({"detail": "Batch no encontrado."}, status=404)
        except AvailabilityConflictError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result, status=status.HTTP_200_OK)

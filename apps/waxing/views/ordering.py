from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Area, AreaCategory, FeaturedItemOrder, Pack, Section
from ..serializers import FeaturedReorderSerializer, UUIDReorderSerializer


def _validate_complete_uuid_list(requested_ids, expected_ids, field_name):
    requested_set = set(requested_ids)
    expected_set = set(expected_ids)
    if requested_set != expected_set or len(requested_ids) != len(expected_ids):
        raise ValidationError(
            {
                field_name: (
                    "Debes enviar la lista completa sin faltantes, extras ni duplicados."
                )
            }
        )


def _single_category_pack_ids(category):
    packs = (
        Pack.objects.filter(section=category.section)
        .prefetch_related("pack_areas__area")
        .all()
    )
    ids = []
    for pack in packs:
        category_ids = {item.area.category_id for item in pack.pack_areas.all()}
        if len(category_ids) == 1 and category.id in category_ids:
            ids.append(pack.id)
    return ids


class CategoryAreaReorderView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, category_id):
        category = get_object_or_404(AreaCategory, id=category_id)
        serializer = UUIDReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_ids = serializer.validated_data["items"]
        expected_ids = list(
            Area.objects.filter(category=category).values_list("id", flat=True)
        )
        _validate_complete_uuid_list(requested_ids, expected_ids, "items")

        area_map = {obj.id: obj for obj in Area.objects.filter(id__in=requested_ids)}
        to_update = []
        for index, area_id in enumerate(requested_ids):
            obj = area_map[area_id]
            if obj.order != index:
                obj.order = index
                to_update.append(obj)

        with transaction.atomic():
            if to_update:
                Area.objects.bulk_update(to_update, ["order"])

        return Response(
            {
                "category_id": category.id,
                "items": [
                    {"id": item_id, "order": idx}
                    for idx, item_id in enumerate(requested_ids)
                ],
            },
            status=status.HTTP_200_OK,
        )


class CategoryPackReorderView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, category_id):
        category = get_object_or_404(AreaCategory, id=category_id)
        serializer = UUIDReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_ids = serializer.validated_data["items"]
        expected_ids = _single_category_pack_ids(category)
        _validate_complete_uuid_list(requested_ids, expected_ids, "items")

        pack_map = {obj.id: obj for obj in Pack.objects.filter(id__in=requested_ids)}
        to_update = []
        for index, pack_id in enumerate(requested_ids):
            obj = pack_map[pack_id]
            if obj.order != index:
                obj.order = index
                to_update.append(obj)

        with transaction.atomic():
            if to_update:
                Pack.objects.bulk_update(to_update, ["order"])

        return Response(
            {
                "category_id": category.id,
                "items": [
                    {"id": item_id, "order": idx}
                    for idx, item_id in enumerate(requested_ids)
                ],
            },
            status=status.HTTP_200_OK,
        )


class SectionFeaturedReorderView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, section_id):
        section = get_object_or_404(Section, id=section_id)
        serializer = FeaturedReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested = serializer.validated_data["items"]
        requested_keys = [(row["item_kind"], row["item_id"]) for row in requested]

        expected_keys = list(
            [("area", area_id) for area_id in Area.objects.filter(
                section=section,
                is_featured=True,
            ).values_list("id", flat=True)]
            + [("pack", pack_id) for pack_id in Pack.objects.filter(
                section=section,
                is_featured=True,
            ).values_list("id", flat=True)]
        )
        if (
            set(requested_keys) != set(expected_keys)
            or len(requested_keys) != len(expected_keys)
        ):
            raise ValidationError(
                {
                    "items": (
                        "Debes enviar la lista completa de destacados sin faltantes, extras ni duplicados."
                    )
                }
            )

        with transaction.atomic():
            FeaturedItemOrder.objects.filter(section=section).delete()
            FeaturedItemOrder.objects.bulk_create(
                [
                    FeaturedItemOrder(
                        section=section,
                        item_kind=item_kind,
                        item_id=item_id,
                        order=index,
                    )
                    for index, (item_kind, item_id) in enumerate(requested_keys)
                ]
            )

        return Response(
            {
                "section_id": section.id,
                "items": [
                    {
                        "item_kind": item_kind,
                        "item_id": item_id,
                        "order": index,
                    }
                    for index, (item_kind, item_id) in enumerate(requested_keys)
                ],
            },
            status=status.HTTP_200_OK,
        )

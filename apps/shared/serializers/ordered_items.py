import json

from rest_framework.exceptions import ValidationError


class OrderedNestedItemsMixin:
    """
    Shared helpers to sync ordered nested item payloads.
    """

    def _normalize_ordered_list(
        self,
        items,
        field_name,
        fill_missing_order,
        *,
        list_error="Debe ser una lista",
        object_error="Cada elemento debe ser un objeto",
    ):
        if items is None:
            return None
        if not isinstance(items, (list, tuple)):
            raise ValidationError({field_name: list_error})

        normalized = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValidationError({field_name: object_error})
            if fill_missing_order and item.get("order") is None:
                item = {**item, "order": index}
            normalized.append(item)
        return normalized

    def _parse_id_list(self, raw, field_name):
        if raw is None:
            return None
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception as exc:
                raise ValidationError({field_name: f"JSON inválido: {exc}"})
        return raw

    def _resequence_ordered_queryset(self, queryset):
        ordered_qs = queryset.order_by("order", "created_at", "id")
        to_update = []
        for index, obj in enumerate(ordered_qs):
            if obj.order != index:
                obj.order = index
                to_update.append(obj)
        if to_update:
            queryset.model.objects.bulk_update(to_update, ["order"])

    def _apply_ordered_changes(
        self,
        *,
        base_qs,
        model_cls,
        items,
        remove_ids,
        field_name,
        update_fields,
        fill_missing_order,
        create_instance,
        not_found_error="El id {item_id} no pertenece a este item",
        list_error="Debe ser una lista",
        object_error="Cada elemento debe ser un objeto",
    ):
        if remove_ids:
            base_qs.filter(id__in=remove_ids).delete()

        if items is None:
            return

        normalized = self._normalize_ordered_list(
            items,
            field_name,
            fill_missing_order,
            list_error=list_error,
            object_error=object_error,
        )
        if not normalized:
            return

        existing = list(base_qs)
        existing_map = {str(obj.id): obj for obj in existing}
        max_order = max([obj.order for obj in existing], default=-1)
        to_create = []
        to_update = []

        for item in normalized:
            item_id = item.get("id")
            payload = dict(item)
            payload.pop("id", None)

            if item_id:
                obj = existing_map.get(str(item_id))
                if not obj:
                    raise ValidationError(
                        {field_name: not_found_error.format(item_id=item_id)}
                    )
                if payload.get("order") is None:
                    payload.pop("order", None)
                for key, value in payload.items():
                    setattr(obj, key, value)
                to_update.append(obj)
            else:
                if payload.get("order") is None:
                    max_order += 1
                    payload["order"] = max_order
                to_create.append(create_instance(payload))

        if to_create:
            model_cls.objects.bulk_create(to_create)
        if to_update:
            model_cls.objects.bulk_update(to_update, update_fields)
        self._resequence_ordered_queryset(base_qs)


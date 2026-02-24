from django.contrib.contenttypes.models import ContentType

from apps.shared.serializers.ordered_items import OrderedNestedItemsMixin


class GenericItemContentSyncMixin(OrderedNestedItemsMixin):
    """
    Helpers for ItemBenefit/ItemRecommendedPoint/ItemFAQ generic relations.
    """

    def _generic_base_queryset(self, instance, model_cls):
        content_type = ContentType.objects.get_for_model(
            instance, for_concrete_model=False
        )
        qs = model_cls.objects.filter(content_type=content_type, object_id=instance.id)
        return content_type, qs

    def _apply_generic_changes(
        self,
        instance,
        model_cls,
        items,
        remove_ids,
        field_name,
        update_fields,
        fill_missing_order,
    ):
        content_type, base_qs = self._generic_base_queryset(instance, model_cls)
        self._apply_ordered_changes(
            base_qs=base_qs,
            model_cls=model_cls,
            items=items,
            remove_ids=remove_ids,
            field_name=field_name,
            update_fields=update_fields,
            fill_missing_order=fill_missing_order,
            create_instance=lambda payload: model_cls(
                content_type=content_type,
                object_id=instance.id,
                **payload,
            ),
            not_found_error="El id {item_id} no pertenece a este item",
            list_error="Debe ser una lista",
            object_error="Cada elemento debe ser un objeto",
        )

    def _resequence_generic_items(self, instance, model_cls):
        _, base_qs = self._generic_base_queryset(instance, model_cls)
        self._resequence_ordered_queryset(base_qs)


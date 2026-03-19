def is_inline_deleted(value):
    return str(value).lower() in {"1", "true", "on", "yes"}


def get_formset_total(data, prefix):
    try:
        return int(data.get(f"{prefix}-TOTAL_FORMS", 0))
    except (TypeError, ValueError):
        return 0


def resolve_inline_prefix(data, model, parent_field_name):
    """
    Prefer the inline prefix actually present in POST data.

    Django admin uses the reverse accessor name as the default inline prefix
    when a ForeignKey defines ``related_name``. Some tests and older payloads
    still use the historical ``<model_name>_set`` shape, so we accept both.
    """
    parent_field = model._meta.get_field(parent_field_name)
    accessor_name = parent_field.remote_field.get_accessor_name()
    legacy_prefix = f"{model._meta.model_name}_set"

    for prefix in (accessor_name, legacy_prefix):
        if prefix and f"{prefix}-TOTAL_FORMS" in data:
            return prefix

    return accessor_name or legacy_prefix

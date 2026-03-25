from django.core.exceptions import ValidationError


FIELD_LABELS = {
    "slug": "Slug",
    "title": "Title",
}


def model_label(model_or_name) -> str:
    if isinstance(model_or_name, str):
        return model_or_name
    return model_or_name.__name__


def field_label(field_name: str) -> str:
    return FIELD_LABELS.get(field_name, field_name.title())


def uniqueness_message(model_or_name, field_name: str) -> str:
    return (
        f"Ya existe {model_label(model_or_name)} con este "
        f"{field_label(field_name)} en esta categoría."
    )


def category_pk(value):
    return getattr(value, "pk", getattr(value, "id", value))


def validate_item_uniqueness(
    *,
    model,
    category,
    slug=None,
    title=None,
    exclude_pk=None,
    cross_model=None,
    include_same_model=True,
    include_cross_model=True,
    error_cls=ValidationError,
):
    category_id = category_pk(category)
    if not category_id:
        return

    if include_same_model:
        _validate_field_in_category(
            model=model,
            field_name="slug",
            value=slug,
            category_id=category_id,
            exclude_pk=exclude_pk,
            error_cls=error_cls,
        )
        _validate_field_in_category(
            model=model,
            field_name="title",
            value=title,
            category_id=category_id,
            exclude_pk=exclude_pk,
            error_cls=error_cls,
        )

    if cross_model is None or not include_cross_model:
        return

    _validate_cross_model_field_in_category(
        model=cross_model,
        field_name="slug",
        value=slug,
        category_id=category_id,
        error_cls=error_cls,
    )
    _validate_cross_model_field_in_category(
        model=cross_model,
        field_name="title",
        value=title,
        category_id=category_id,
        error_cls=error_cls,
    )


def _validate_field_in_category(
    *,
    model,
    field_name: str,
    value,
    category_id,
    exclude_pk=None,
    error_cls=ValidationError,
):
    if not value or not category_id:
        return

    lookup = {f"{field_name}__iexact": value, "category_id": category_id}
    qs = model.objects.filter(**lookup)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise error_cls({field_name: [uniqueness_message(model, field_name)]})


def _validate_cross_model_field_in_category(
    *,
    model,
    field_name: str,
    value,
    category_id,
    error_cls=ValidationError,
):
    if not value or not category_id:
        return

    lookup = {f"{field_name}__iexact": value, "category_id": category_id}
    if model.objects.filter(**lookup).exists():
        raise error_cls({field_name: [uniqueness_message(model, field_name)]})

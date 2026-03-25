from django.core.exceptions import ValidationError as DjangoValidationError

from ..services.uniqueness import validate_item_uniqueness


class PerCategoryUniquenessFormMixin:
    uniqueness_model = None
    cross_uniqueness_model = None

    def validate_per_category_uniqueness(self, cleaned):
        model = self.uniqueness_model or getattr(self._meta, "model", None)
        if model is None:
            return

        category = cleaned.get("category")
        slug = cleaned.get("slug")
        title = cleaned.get("title")

        if self.instance and self.instance.pk:
            category = category or self.instance.category_id
            slug = slug or self.instance.slug
            title = title or self.instance.title

        validate_item_uniqueness(
            model=model,
            category=category,
            slug=slug,
            title=title,
            exclude_pk=getattr(self.instance, "pk", None),
            cross_model=self.cross_uniqueness_model,
            include_same_model=False,
            error_cls=DjangoValidationError,
        )

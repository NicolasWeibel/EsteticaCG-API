# apps/catalog/admin/combo.py
from django import forms
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.html import format_html

from ..models import (
    Combo,
    ComboIngredient,
    ComboSessionItem,
    ComboMedia,
    ItemBenefit,
    ItemRecommendedPoint,
    ItemFAQ,
)
from .mixins import CloudinaryMediaAdminMixin
from ..services.validation import (
    validate_combo_rules,
    validate_combo_treatments_active,
    validate_optional_gt_zero_or_null,
)
from ..services.combo_sessions import prune_session_items_for_sessions
from .utils import get_formset_total, is_inline_deleted
from ..utils.media import build_media_url


class ComboAdminForm(forms.ModelForm):
    class Meta:
        model = Combo
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not self.is_bound:
            return cleaned

        is_active = cleaned.get(
            "is_active",
            self.instance.is_active if self.instance else False,
        )
        sessions = cleaned.get(
            "sessions",
            self.instance.sessions if self.instance else 0,
        )
        duration = cleaned.get(
            "duration",
            self.instance.duration if self.instance else None,
        )

        ingredient_prefix = f"{ComboIngredient._meta.model_name}_set"
        ingredient_total = get_formset_total(self.data, ingredient_prefix)
        ingredient_ids = []
        treatment_zone_config_ids = []
        for idx in range(ingredient_total):
            if is_inline_deleted(self.data.get(f"{ingredient_prefix}-{idx}-DELETE")):
                continue
            tzc_val = self.data.get(f"{ingredient_prefix}-{idx}-treatment_zone_config")
            if not tzc_val:
                continue
            treatment_zone_config_ids.append(tzc_val)
            ing_id = self.data.get(f"{ingredient_prefix}-{idx}-id")
            if ing_id:
                ingredient_ids.append(ing_id)
            else:
                ingredient_ids.append(f"__new__{idx}")

        session_prefix = f"{ComboSessionItem._meta.model_name}_set"
        session_total = get_formset_total(self.data, session_prefix)
        existing_session_indices = {}
        if self.instance and self.instance.pk:
            existing_session_indices = {
                str(obj.id): obj.session_index
                for obj in self.instance.session_items.only("id", "session_index")
            }
        session_items = []
        for idx in range(session_total):
            if is_inline_deleted(self.data.get(f"{session_prefix}-{idx}-DELETE")):
                continue
            row_id = self.data.get(f"{session_prefix}-{idx}-id")
            session_index_raw = self.data.get(f"{session_prefix}-{idx}-session_index")
            ingredient_raw = self.data.get(f"{session_prefix}-{idx}-ingredient")
            if not session_index_raw and not ingredient_raw:
                continue
            try:
                session_index = int(session_index_raw)
            except (TypeError, ValueError):
                session_index = session_index_raw

            row_id_key = str(row_id) if row_id else None
            is_legacy_podable = (
                row_id_key in existing_session_indices
                and isinstance(session_index, int)
                and session_index > (sessions or 0)
                and existing_session_indices[row_id_key] == session_index
            )
            if is_legacy_podable:
                continue

            session_items.append(
                {
                    "session_index": session_index,
                    "ingredient": ingredient_raw,
                }
            )

        try:
            validate_combo_rules(
                is_active=is_active,
                sessions=sessions or 0,
                ingredient_ids=ingredient_ids,
                session_items=session_items,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, messages in exc.message_dict.items():
                    target = field if field in self.fields else None
                    for message in messages:
                        self.add_error(target, message)
            else:
                self.add_error(None, exc)

        try:
            validate_combo_treatments_active(
                is_active=is_active,
                treatment_zone_config_ids=treatment_zone_config_ids,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, messages in exc.message_dict.items():
                    target = field if field in self.fields else None
                    for message in messages:
                        self.add_error(target, message)
            else:
                self.add_error(None, exc)

        try:
            validate_optional_gt_zero_or_null(
                field_name="duration",
                value=duration,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, messages in exc.message_dict.items():
                    target = field if field in self.fields else None
                    for message in messages:
                        self.add_error(target, message)
            else:
                self.add_error(None, exc)

        return cleaned


class ComboIngredientInline(admin.TabularInline):
    model = ComboIngredient
    extra = 1
    autocomplete_fields = ("treatment_zone_config",)


class ComboSessionItemInline(admin.TabularInline):
    model = ComboSessionItem
    extra = 1
    fields = ("session_index", "ingredient")


class ComboMediaInline(admin.TabularInline):
    model = ComboMedia
    extra = 1
    fields = ("media_preview", "media", "media_type", "alt_text", "order")
    readonly_fields = ("media_preview",)
    ordering = ("order",)

    def media_preview(self, obj):
        if obj.media:
            url = build_media_url(obj.media, obj.media_type)
            if getattr(obj, "media_type", "image") == "video":
                return format_html(
                    '<video src="{}" controls muted preload="metadata" style="height: 80px; border-radius: 5px;"></video>',
                    url,
                )
            return format_html(
                '<img src="{}" style="height: 80px; border-radius: 5px;" />',
                url,
            )
        return ""


class ItemBenefitInline(GenericTabularInline):
    model = ItemBenefit
    extra = 1
    fields = ("title", "detail", "order")
    ordering = ("order",)


class ItemRecommendedPointInline(GenericTabularInline):
    model = ItemRecommendedPoint
    extra = 1
    fields = ("title", "detail", "order")
    ordering = ("order",)


class ItemFAQInline(GenericTabularInline):
    model = ItemFAQ
    extra = 1
    fields = ("question", "answer", "order")
    ordering = ("order",)


@admin.register(Combo)
class ComboAdmin(CloudinaryMediaAdminMixin, admin.ModelAdmin):
    form = ComboAdminForm
    list_display = (
        "media_preview_list",  # 👈 Foto
        "title",
        "slug",
        "category",
        "journey",
        "price",
        "promotional_price",
        "sessions",
        "duration",
        "min_session_interval_days",
        "session_freq",
        "session_interval",
        "occurrences_per_period",
        "order",
        "is_active",
        "is_featured",
    )
    list_editable = ("order", "is_active", "is_featured")
    list_filter = ("category", "journey", "is_active", "is_featured")
    search_fields = ("title", "description", "slug")
    inlines = [
        ComboMediaInline,
        ItemBenefitInline,
        ItemRecommendedPointInline,
        ItemFAQInline,
        ComboIngredientInline,
        ComboSessionItemInline,
    ]

    # Preview en readonly
    readonly_fields = ("media_preview_detail", "id", "created_at", "updated_at")

    autocomplete_fields = (
        "category",
        "journey",
        "tags",
        "techniques",
        "objectives",
        "intensities",
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        prune_session_items_for_sessions(form.instance)

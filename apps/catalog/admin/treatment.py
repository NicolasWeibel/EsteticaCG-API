# apps/catalog/admin/treatment.py
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.html import format_html

from ..models import (
    Combo,
    Treatment,
    TreatmentZoneConfig,
    TreatmentMedia,
)
from .uniqueness import PerCategoryUniquenessFormMixin
from .item_content_inlines import (
    ItemBenefitInline,
    ItemFAQInline,
    ItemRecommendedPointInline,
)
from .incompatibility import IncompatibilityInline, IncompatibilityInlineReverse
from .mixins import CloudinaryMediaAdminMixin  # ?? Importamos
from ..services.validation import validate_treatment_rules
from .utils import get_formset_total, is_inline_deleted, resolve_inline_prefix
from ..utils.media import build_media_url


class TreatmentAdminForm(PerCategoryUniquenessFormMixin, forms.ModelForm):
    cross_uniqueness_model = Combo

    class Meta:
        model = Treatment
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not self.is_bound:
            return cleaned

        is_active = cleaned.get(
            "is_active",
            self.instance.is_active if self.instance else False,
        )
        requires_zones = cleaned.get(
            "requires_zones",
            self.instance.requires_zones if self.instance else False,
        )

        zone_prefix = resolve_inline_prefix(
            self.data,
            TreatmentZoneConfig,
            "treatment",
        )
        zone_total = get_formset_total(self.data, zone_prefix)
        has_zones = False
        for idx in range(zone_total):
            if is_inline_deleted(self.data.get(f"{zone_prefix}-{idx}-DELETE")):
                continue
            zone_val = self.data.get(f"{zone_prefix}-{idx}-zone")
            if zone_val:
                has_zones = True
                break

        try:
            self.validate_per_category_uniqueness(cleaned)
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, messages in exc.message_dict.items():
                    target = field if field in self.fields else None
                    for message in messages:
                        self.add_error(target, message)
            else:
                self.add_error(None, exc)

        try:
            validate_treatment_rules(
                is_active=is_active,
                requires_zones=requires_zones,
                has_zones=has_zones,
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


class TreatmentZoneConfigInline(admin.StackedInline):
    model = TreatmentZoneConfig
    extra = 0
    fields = ("zone", "duration", "body_position", "price", "promotional_price")
    autocomplete_fields = ("zone",)
    show_change_link = True


class TreatmentMediaInline(admin.TabularInline):
    model = TreatmentMedia
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


@admin.register(TreatmentZoneConfig)
class TreatmentZoneConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "treatment",
        "zone",
        "body_position",
        "duration",
        "price",
        "promotional_price",
    )
    list_filter = ("treatment__category", "zone", "body_position")
    search_fields = ("treatment__title", "zone__name")
    inlines = [IncompatibilityInline, IncompatibilityInlineReverse]
    autocomplete_fields = ("treatment", "zone")


@admin.register(Treatment)
class TreatmentAdmin(CloudinaryMediaAdminMixin, admin.ModelAdmin):
    form = TreatmentAdminForm
    list_display = (
        "media_preview_list",  # ?? Agregamos foto
        "title",
        "slug",
        "category",
        "journey",
        "order",
        "is_active",
        "is_featured",
    )
    list_editable = ("order", "is_active", "is_featured")
    list_filter = (
        "category",
        "journey",
        "techniques",
        "intensities",
        "is_active",
        "is_featured",
    )
    search_fields = ("title", "description", "slug")
    inlines = [
        TreatmentMediaInline,
        ItemBenefitInline,
        ItemRecommendedPointInline,
        ItemFAQInline,
        TreatmentZoneConfigInline,
    ]

    # Agregamos el preview a readonly
    readonly_fields = ("media_preview_detail", "id", "created_at", "updated_at")

    autocomplete_fields = (
        "category",
        "journey",
        "techniques",
        "objectives",
        "intensities",
        "tags",
    )

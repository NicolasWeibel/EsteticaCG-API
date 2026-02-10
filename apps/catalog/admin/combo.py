# apps/catalog/admin/combo.py
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
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
from ..utils.media import build_media_url


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
        "treatment_types",
        "objectives",
        "intensities",
    )

# apps/catalog/admin/journey.py
from django.contrib import admin
from django.utils.html import format_html

from ..models import Journey, JourneyMedia
from .item_content_inlines import (
    ItemBenefitInline,
    ItemFAQInline,
    ItemRecommendedPointInline,
)
from .mixins import CloudinaryMediaAdminMixin
from ..utils.media import build_media_url


class JourneyMediaInline(admin.TabularInline):
    model = JourneyMedia
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


@admin.register(Journey)
class JourneyAdmin(CloudinaryMediaAdminMixin, admin.ModelAdmin):
    list_display = ("media_preview_list", "title", "slug", "category")
    list_filter = ("category",)
    search_fields = ("title", "description", "slug")
    readonly_fields = ("id", "created_at", "updated_at", "media_preview_detail")
    autocomplete_fields = ("category",)
    inlines = [
        JourneyMediaInline,
        ItemBenefitInline,
        ItemRecommendedPointInline,
        ItemFAQInline,
    ]

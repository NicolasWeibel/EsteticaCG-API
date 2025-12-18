# apps/catalog/admin/journey.py
from django.contrib import admin
from django.utils.html import format_html

from ..models import Journey, JourneyImage
from .mixins import CloudinaryImageAdminMixin


class JourneyImageInline(admin.TabularInline):
    model = JourneyImage
    extra = 1
    fields = ("image_preview", "image", "alt_text", "order")
    readonly_fields = ("image_preview",)
    ordering = ("order",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height: 80px; border-radius: 5px;" />',
                obj.image.url,
            )
        return ""


@admin.register(Journey)
class JourneyAdmin(CloudinaryImageAdminMixin, admin.ModelAdmin):
    list_display = ("image_preview_list", "title", "slug", "category")
    list_filter = ("category",)
    search_fields = ("title", "description", "slug")
    readonly_fields = ("id", "created_at", "updated_at", "image_preview_detail")
    autocomplete_fields = ("category",)
    inlines = [JourneyImageInline]

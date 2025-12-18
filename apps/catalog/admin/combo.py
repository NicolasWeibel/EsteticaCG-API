# apps/catalog/admin/combo.py
from django.contrib import admin
from django.utils.html import format_html

from ..models import Combo, ComboIngredient, ComboStep, ComboStepItem, ComboImage
from .mixins import CloudinaryImageAdminMixin


class ComboIngredientInline(admin.TabularInline):
    model = ComboIngredient
    extra = 1
    autocomplete_fields = ("treatment_zone_config",)


class ComboStepItemInline(admin.TabularInline):
    model = ComboStepItem
    extra = 1
    fields = ("treatment", "zone", "duration", "order_hint")
    autocomplete_fields = ("treatment", "zone")


class ComboStepInline(admin.StackedInline):
    model = ComboStep
    extra = 1
    show_change_link = True


class ComboImageInline(admin.TabularInline):
    model = ComboImage
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


@admin.register(Combo)
class ComboAdmin(CloudinaryImageAdminMixin, admin.ModelAdmin):
    list_display = (
        "image_preview_list",  # 👈 Foto
        "title",
        "slug",
        "category",
        "journey",
        "price",
        "promotional_price",
        "sessions",
        "min_session_interval_days",
        "order",
        "is_active",
        "is_featured",
    )
    list_editable = ("order", "is_active", "is_featured")
    list_filter = ("category", "journey", "is_active", "is_featured")
    search_fields = ("title", "description", "slug")
    inlines = [ComboImageInline, ComboIngredientInline, ComboStepInline]

    # Preview en readonly
    readonly_fields = ("image_preview_detail", "id", "created_at", "updated_at")

    autocomplete_fields = ("category", "journey")

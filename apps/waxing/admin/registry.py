from django.contrib import admin
from django.utils.html import format_html

from ..models import (
    Area,
    AreaCategory,
    BenefitItem,
    FaqItem,
    FeaturedItemOrder,
    Pack,
    PackArea,
    RecommendationItem,
    Section,
    WaxingContent,
    WaxingSettings,
)
from .mixins import ImagePreviewAdminMixin, SingletonAdminMixin


class PackAreaInline(admin.TabularInline):
    model = PackArea
    extra = 1
    fields = ("area", "order")
    autocomplete_fields = ("area",)
    ordering = ("order",)


class FeaturedItemOrderInline(admin.TabularInline):
    model = FeaturedItemOrder
    extra = 1
    fields = ("item_kind", "item_id", "order")
    ordering = ("order",)


class BenefitItemInline(admin.TabularInline):
    model = BenefitItem
    extra = 1
    fields = ("title", "detail", "order", "is_active")
    ordering = ("order",)


class RecommendationItemInline(admin.TabularInline):
    model = RecommendationItem
    extra = 1
    fields = ("title", "detail", "order", "is_active")
    ordering = ("order",)


class FaqItemInline(admin.TabularInline):
    model = FaqItem
    extra = 1
    fields = ("question", "answer", "order", "is_active")
    ordering = ("order",)


@admin.register(WaxingSettings)
class WaxingSettingsAdmin(SingletonAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "is_enabled",
        "public_visible",
        "maintenance_mode",
        "allow_booking",
        "show_prices",
        "featured_enabled",
    )
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Section)
class SectionAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = ("image_preview_list", "name", "is_active", "featured_sort")
    list_filter = ("name", "is_active", "featured_sort")
    search_fields = ("name",)
    inlines = [FeaturedItemOrderInline]
    readonly_fields = ("image_preview_detail", "id", "created_at", "updated_at")
    fields = (
        "id",
        "image_preview_detail",
        "name",
        "image",
        "is_active",
        "featured_sort",
        "created_at",
        "updated_at",
    )


@admin.register(AreaCategory)
class AreaCategoryAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = (
        "image_preview_list",
        "name",
        "section",
        "order",
        "is_active",
        "show_packs",
    )
    list_editable = ("order", "is_active", "show_packs")
    list_filter = ("section", "is_active", "show_packs", "area_sort", "pack_sort")
    search_fields = ("name", "short_description")
    readonly_fields = ("image_preview_detail", "id", "created_at", "updated_at")
    autocomplete_fields = ("section",)
    fields = (
        "id",
        "image_preview_detail",
        "section",
        "name",
        "short_description",
        "description",
        "image",
        "order",
        "is_active",
        "show_packs",
        "area_sort",
        "pack_sort",
        "pack_position",
        "created_at",
        "updated_at",
    )


@admin.register(Area)
class AreaAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = (
        "image_preview_list",
        "name",
        "section",
        "category",
        "price",
        "promotional_price",
        "order",
        "is_active",
        "is_featured",
    )
    list_editable = ("order", "is_active", "is_featured")
    list_filter = ("section", "category", "is_active", "is_featured")
    search_fields = ("name", "short_description", "description")
    readonly_fields = ("image_preview_detail", "id", "created_at", "updated_at")
    autocomplete_fields = ("section", "category")
    fields = (
        "id",
        "image_preview_detail",
        "section",
        "category",
        "name",
        "price",
        "promotional_price",
        "short_description",
        "description",
        "image",
        "order",
        "is_active",
        "is_featured",
        "created_at",
        "updated_at",
    )


@admin.register(Pack)
class PackAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = (
        "image_preview_list",
        "name",
        "section",
        "price",
        "promotional_price",
        "order",
        "is_active",
        "is_featured",
    )
    list_editable = ("order", "is_active", "is_featured")
    list_filter = ("section", "is_active", "is_featured")
    search_fields = ("name", "short_description", "description")
    inlines = [PackAreaInline]
    readonly_fields = ("image_preview_detail", "id", "created_at", "updated_at")
    autocomplete_fields = ("section",)
    fields = (
        "id",
        "image_preview_detail",
        "section",
        "name",
        "price",
        "promotional_price",
        "short_description",
        "description",
        "image",
        "order",
        "is_active",
        "is_featured",
        "created_at",
        "updated_at",
    )


@admin.register(PackArea)
class PackAreaAdmin(admin.ModelAdmin):
    list_display = ("pack", "area", "order")
    list_filter = ("pack__section", "area__category")
    search_fields = ("pack__name", "area__name")
    autocomplete_fields = ("pack", "area")


@admin.register(FeaturedItemOrder)
class FeaturedItemOrderAdmin(admin.ModelAdmin):
    list_display = ("section", "item_kind", "item_id", "order")
    list_filter = ("section", "item_kind")
    search_fields = ("item_id",)
    autocomplete_fields = ("section",)


@admin.register(WaxingContent)
class WaxingContentAdmin(SingletonAdminMixin, admin.ModelAdmin):
    list_display = ("title", "created_at", "updated_at")
    search_fields = ("title", "description")
    inlines = [BenefitItemInline, RecommendationItemInline, FaqItemInline]
    readonly_fields = (
        "image_preview",
        "benefits_image_preview",
        "recommendations_image_preview",
        "id",
        "created_at",
        "updated_at",
    )
    fields = (
        "title",
        "short_description",
        "description",
        "recommendations_intro_text",
        "image_preview",
        "image",
        "benefits_image_preview",
        "benefits_image",
        "recommendations_image_preview",
        "recommendations_image",
        "id",
        "created_at",
        "updated_at",
    )

    def image_preview(self, obj):
        if not obj or not obj.image:
            return "Sin imagen"
        return format_html(
            '<img src="{}" style="max-width: 240px; border-radius: 8px;" />',
            obj.image.url,
        )

    image_preview.short_description = "Preview principal"

    def benefits_image_preview(self, obj):
        if not obj or not obj.benefits_image:
            return "Sin imagen"
        return format_html(
            '<img src="{}" style="max-width: 240px; border-radius: 8px;" />',
            obj.benefits_image.url,
        )

    benefits_image_preview.short_description = "Preview beneficios"

    def recommendations_image_preview(self, obj):
        if not obj or not obj.recommendations_image:
            return "Sin imagen"
        return format_html(
            '<img src="{}" style="max-width: 240px; border-radius: 8px;" />',
            obj.recommendations_image.url,
        )

    recommendations_image_preview.short_description = "Preview recomendaciones"


@admin.register(BenefitItem)
class BenefitItemAdmin(admin.ModelAdmin):
    list_display = ("title", "content", "order", "is_active")
    list_filter = ("is_active", "content")
    search_fields = ("title", "detail")
    autocomplete_fields = ("content",)


@admin.register(RecommendationItem)
class RecommendationItemAdmin(admin.ModelAdmin):
    list_display = ("title", "content", "order", "is_active")
    list_filter = ("is_active", "content")
    search_fields = ("title", "detail")
    autocomplete_fields = ("content",)


@admin.register(FaqItem)
class FaqItemAdmin(admin.ModelAdmin):
    list_display = ("question", "content", "order", "is_active")
    list_filter = ("is_active", "content")
    search_fields = ("question", "answer")
    autocomplete_fields = ("content",)

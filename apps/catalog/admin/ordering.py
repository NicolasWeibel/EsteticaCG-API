from django.contrib import admin

from ..models import ItemOrder, Placement, PlacementItem


class PlacementItemInline(admin.TabularInline):
    model = PlacementItem
    extra = 1
    fields = ("item_kind", "item_id", "order")
    ordering = ("order",)


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "max_items", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "slug")
    inlines = [PlacementItemInline]


@admin.register(ItemOrder)
class ItemOrderAdmin(admin.ModelAdmin):
    list_display = ("context_kind", "context_id", "item_kind", "item_id", "order")
    list_filter = ("context_kind", "item_kind")
    search_fields = ("context_id", "item_id")

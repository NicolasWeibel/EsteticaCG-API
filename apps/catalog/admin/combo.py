from django.contrib import admin
from ..models import Combo, ComboIngredient, ComboStep, ComboStepItem


class ComboIngredientInline(admin.TabularInline):
    model = ComboIngredient
    extra = 1
    autocomplete_fields = ("treatment", "zone")


class ComboStepItemInline(admin.TabularInline):
    model = ComboStepItem
    extra = 1
    fields = ("treatment", "zone", "duration", "order_hint")
    autocomplete_fields = ("treatment", "zone")


class ComboStepInline(admin.StackedInline):
    model = ComboStep
    extra = 1
    show_change_link = True


@admin.register(Combo)
class ComboAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "category",
        "journey",
        "price",
        "promotional_price",
        "order",
        "is_active",
        "is_featured",
    )
    list_editable = ("order", "is_active", "is_featured")
    list_filter = ("category", "journey", "is_active", "is_featured")
    search_fields = ("title", "description", "slug")
    inlines = [ComboIngredientInline, ComboStepInline]
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("category", "journey")

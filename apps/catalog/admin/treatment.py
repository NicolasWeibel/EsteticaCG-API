from django.contrib import admin
from ..models import Treatment, TreatmentZoneConfig
from .incompatibility import IncompatibilityInline, IncompatibilityInlineReverse


class TreatmentZoneConfigInline(admin.StackedInline):
    model = TreatmentZoneConfig
    extra = 0
    fields = ("zone", "duration", "body_position", "price", "promotional_price")
    autocomplete_fields = ("zone",)
    show_change_link = True


@admin.register(TreatmentZoneConfig)
class TreatmentZoneConfigAdmin(admin.ModelAdmin):
    list_display = (
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
class TreatmentAdmin(admin.ModelAdmin):
    list_display = (
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
        "treatment_types",
        "intensities",
        "is_active",
        "is_featured",
    )
    search_fields = ("title", "description", "slug")
    inlines = [TreatmentZoneConfigInline]
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = (
        "category",
        "journey",
        "treatment_types",
        "objectives",
        "intensities",
        "durations",
    )

# apps/catalog/admin/treatment.py
from django.contrib import admin
from ..models import Treatment, TreatmentZoneConfig
from .incompatibility import IncompatibilityInline, IncompatibilityInlineReverse
from .mixins import CloudinaryImageAdminMixin  # 👈 Importamos


class TreatmentZoneConfigInline(admin.StackedInline):
    model = TreatmentZoneConfig
    extra = 0
    fields = ("zone", "duration", "body_position", "price", "promotional_price")
    autocomplete_fields = ("zone",)
    show_change_link = True


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
class TreatmentAdmin(CloudinaryImageAdminMixin, admin.ModelAdmin):  # 👈 Heredamos
    list_display = (
        "image_preview_list",  # 👈 Agregamos foto
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

    # Agregamos el preview a readonly
    readonly_fields = ("image_preview_detail", "id", "created_at", "updated_at")

    autocomplete_fields = (
        "category",
        "journey",
        "treatment_types",
        "objectives",
        "intensities",
        "durations",
    )

# apps/catalog/admin/filters.py
from django.contrib import admin
from ..models import TreatmentType, Objective, IntensityLevel, Tag
from .mixins import CloudinaryMediaAdminMixin


@admin.register(TreatmentType)
class TreatmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Objective)
class ObjectiveAdmin(CloudinaryMediaAdminMixin, admin.ModelAdmin):
    # Cambiamos "image" (la URL cruda) por "media_preview_list"
    list_display = ("media_preview_list", "name", "category")
    search_fields = ("name",)
    readonly_fields = ("media_preview_detail",)  # Detalle visual
    autocomplete_fields = ("category",)


@admin.register(IntensityLevel)
class IntensityLevelAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

# apps/catalog/admin/filters.py
from django.contrib import admin
from ..models import Technique, Objective, Intensity, Tag
from .mixins import CloudinaryMediaAdminMixin


@admin.register(Technique)
class TechniqueAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name",)
    list_filter = ("category",)
    autocomplete_fields = ("category",)


@admin.register(Objective)
class ObjectiveAdmin(CloudinaryMediaAdminMixin, admin.ModelAdmin):
    # Cambiamos "image" (la URL cruda) por "media_preview_list"
    list_display = ("media_preview_list", "name", "category")
    search_fields = ("name",)
    readonly_fields = ("media_preview_detail",)  # Detalle visual
    autocomplete_fields = ("category",)


@admin.register(Intensity)
class IntensityAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name",)
    list_filter = ("category",)
    autocomplete_fields = ("category",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

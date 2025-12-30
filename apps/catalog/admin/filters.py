# apps/catalog/admin/filters.py
from django.contrib import admin
from ..models import TreatmentType, Objective, IntensityLevel, DurationBucket, Tag
from .mixins import CloudinaryImageAdminMixin


@admin.register(TreatmentType)
class TreatmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Objective)
class ObjectiveAdmin(CloudinaryImageAdminMixin, admin.ModelAdmin):
    # Cambiamos "image" (la URL cruda) por "image_preview_list"
    list_display = ("image_preview_list", "name")
    search_fields = ("name",)
    readonly_fields = ("image_preview_detail",)  # Detalle visual


@admin.register(IntensityLevel)
class IntensityLevelAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(DurationBucket)
class DurationBucketAdmin(admin.ModelAdmin):
    list_display = ("name", "minutes")
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

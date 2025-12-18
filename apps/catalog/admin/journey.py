# apps/catalog/admin/journey.py
from django.contrib import admin
from ..models import Journey
from .mixins import CloudinaryImageAdminMixin


@admin.register(Journey)
class JourneyAdmin(CloudinaryImageAdminMixin, admin.ModelAdmin):
    list_display = ("image_preview_list", "title", "slug", "category")
    list_filter = ("category",)
    search_fields = ("title", "description", "slug")
    readonly_fields = ("id", "created_at", "updated_at", "image_preview_detail")
    autocomplete_fields = ("category",)

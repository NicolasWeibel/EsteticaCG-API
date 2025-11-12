from django.contrib import admin
from ..models import Journey


@admin.register(Journey)
class JourneyAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "category")
    list_filter = ("category",)
    search_fields = ("title", "description", "slug")
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("category",)

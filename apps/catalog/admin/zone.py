from django.contrib import admin
from ..models import Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name",)
    list_filter = ("category",)
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("category",)

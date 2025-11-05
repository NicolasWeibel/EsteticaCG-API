from django.contrib import admin
from .models import Treatment


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "base_price",
        "is_active",
        "is_featured",
        "updated_at",
    )
    search_fields = ("name",)
    list_filter = ("is_active", "is_featured")

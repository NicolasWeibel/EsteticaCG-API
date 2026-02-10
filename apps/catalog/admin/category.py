# apps/catalog/admin/category.py
from django.contrib import admin
from ..models import Category
from .mixins import CloudinaryMediaAdminMixin  # 👈 Importamos


@admin.register(Category)
class CategoryAdmin(CloudinaryMediaAdminMixin, admin.ModelAdmin):  # 👈 Heredamos
    list_display = ("media_preview_list", "name", "slug")  # Agregamos la columna
    search_fields = ("name", "slug")
    readonly_fields = ("media_preview_detail",)  # Agregamos el detalle

    # Opcional: Para ver la foto al editar
    fields = (
        "media_preview_detail",
        "image",
        "name",
        "slug",
        "include_journeys",
        "journey_position",
        "default_sort",
        "seo_title",
        "seo_description",
    )

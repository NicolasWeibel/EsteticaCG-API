# apps/catalog/admin/mixins.py
from django.utils.html import format_html


class CloudinaryImageAdminMixin:
    """
    Mixin para mostrar miniaturas de Cloudinary en listas y detalles.
    """

    def image_preview_list(self, obj):
        if obj.image:
            # Transformación: 50x50, recorte centrado (face detection si es posible), formato auto
            url = obj.image.url.replace(
                "/upload/", "/upload/w_50,h_50,c_fill,g_face,q_auto,f_auto/"
            )
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%; object-fit: cover;" />',
                url,
            )
        return "—"

    image_preview_list.short_description = "Img"

    def image_preview_detail(self, obj):
        if obj.image:
            # Transformación: Ancho 300px, altura proporcional
            url = obj.image.url.replace(
                "/upload/", "/upload/w_300,c_limit,q_auto,f_auto/"
            )
            return format_html(
                '<img src="{}" style="border-radius: 8px; max-width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" />',
                url,
            )
        return "Sin imagen"

    image_preview_detail.short_description = "Vista Previa"

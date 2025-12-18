# apps/catalog/admin/mixins.py
from django.utils.html import format_html


class CloudinaryImageAdminMixin:
    """
    Mixin para mostrar miniaturas de Cloudinary en listas y detalles.
    """

    def _get_primary_image(self, obj):
        gallery = getattr(obj, "images", None)
        if gallery is not None:
            first = gallery.first()
            if first and getattr(first, "image", None):
                return first.image
        return getattr(obj, "image", None)

    def image_preview_list(self, obj):
        image_field = self._get_primary_image(obj)
        if image_field:
            url = image_field.url.replace(
                "/upload/", "/upload/w_50,h_50,c_fill,g_face,q_auto,f_auto/"
            )
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%; object-fit: cover;" />',
                url,
            )
        return "-"

    image_preview_list.short_description = "Img"

    def image_preview_detail(self, obj):
        image_field = self._get_primary_image(obj)
        if image_field:
            url = image_field.url.replace(
                "/upload/", "/upload/w_300,c_limit,q_auto,f_auto/"
            )
            return format_html(
                '<img src="{}" style="border-radius: 8px; max-width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" />',
                url,
            )
        return "Sin imagen"

    image_preview_detail.short_description = "Vista Previa"

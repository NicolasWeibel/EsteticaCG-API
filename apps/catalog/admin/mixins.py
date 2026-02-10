# apps/catalog/admin/mixins.py
from django.utils.html import format_html

from ..utils.media import build_media_url


class CloudinaryMediaAdminMixin:
    """
    Mixin para mostrar miniaturas de Cloudinary en listas y detalles.
    """

    def _get_primary_media(self, obj):
        gallery = getattr(obj, "media", None)
        if gallery is not None:
            first = gallery.first()
            if first and getattr(first, "media", None):
                return first.media, getattr(first, "media_type", "image")
        image_field = getattr(obj, "image", None)
        if image_field:
            return image_field, "image"
        return None, None

    def media_preview_list(self, obj):
        media_field, media_type = self._get_primary_media(obj)
        if media_field:
            if media_type == "video":
                return format_html(
                    '<span style="font-size: 12px; color: #666;">Video</span>'
                )
            url = build_media_url(media_field, media_type).replace(
                "/upload/", "/upload/w_50,h_50,c_fill,g_face,q_auto,f_auto/"
            )
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 50%; object-fit: cover;" />',
                url,
            )
        return "-"

    media_preview_list.short_description = "Media"

    def media_preview_detail(self, obj):
        media_field, media_type = self._get_primary_media(obj)
        if media_field:
            if media_type == "video":
                return format_html(
                    '<video src="{}" controls muted preload="metadata" style="border-radius: 8px; max-width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"></video>',
                    build_media_url(media_field, media_type),
                )
            url = build_media_url(media_field, media_type).replace(
                "/upload/", "/upload/w_300,c_limit,q_auto,f_auto/"
            )
            return format_html(
                '<img src="{}" style="border-radius: 8px; max-width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" />',
                url,
            )
        return "Sin media"

    media_preview_detail.short_description = "Vista Previa"

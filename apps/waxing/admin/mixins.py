from django.utils.html import format_html
from django.shortcuts import redirect
from django.urls import reverse


class ImagePreviewAdminMixin:
    def image_preview_list(self, obj):
        image = getattr(obj, "image", None)
        if not image:
            return "-"
        try:
            url = image.url
        except Exception:
            return "-"
        return format_html(
            '<img src="{}" width="50" height="50" style="border-radius: 8px; object-fit: cover;" />',
            url,
        )

    image_preview_list.short_description = "Imagen"

    def image_preview_detail(self, obj):
        image = getattr(obj, "image", None)
        if not image:
            return "Sin imagen"
        try:
            url = image.url
        except Exception:
            return "Sin imagen"
        return format_html(
            '<img src="{}" style="max-width: 360px; border-radius: 8px; object-fit: contain;" />',
            url,
        )

    image_preview_detail.short_description = "Vista previa"


class SingletonAdminMixin:
    """
    Fuerza UX de singleton en admin:
    - no permite crear un segundo registro
    - no permite borrar desde admin
    - redirige el changelist directo al objeto unico
    """

    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.objects.first()
        if obj:
            url = reverse(
                f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                args=[obj.pk],
            )
            return redirect(url)
        return super().changelist_view(request, extra_context=extra_context)

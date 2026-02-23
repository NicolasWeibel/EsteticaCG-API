import cloudinary.uploader
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Area, AreaCategory, Pack, Section, WaxingContent


def _cleanup_cloudinary_image(image_field):
    if not image_field:
        return
    try:
        cloudinary.uploader.destroy(image_field.name, resource_type="image")
    except Exception:
        # La limpieza es best-effort para evitar romper el flujo de borrado.
        pass


@receiver(post_delete, sender=Section)
def cleanup_section_image(sender, instance, **kwargs):
    _cleanup_cloudinary_image(instance.image)


@receiver(post_delete, sender=AreaCategory)
def cleanup_area_category_image(sender, instance, **kwargs):
    _cleanup_cloudinary_image(instance.image)


@receiver(post_delete, sender=Area)
def cleanup_area_image(sender, instance, **kwargs):
    _cleanup_cloudinary_image(instance.image)


@receiver(post_delete, sender=Pack)
def cleanup_pack_image(sender, instance, **kwargs):
    _cleanup_cloudinary_image(instance.image)


@receiver(post_delete, sender=WaxingContent)
def cleanup_waxing_content_images(sender, instance, **kwargs):
    _cleanup_cloudinary_image(instance.image)
    _cleanup_cloudinary_image(instance.benefits_image)
    _cleanup_cloudinary_image(instance.recommendations_image)

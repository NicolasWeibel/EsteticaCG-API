import cloudinary.uploader
from django.db.models.signals import post_delete, post_save, pre_save
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


def _capture_old_image_for_cleanup(instance, field_name):
    """
    Capture old image reference before saving (pre_save).
    Stores it temporarily so we can delete it AFTER the new one is saved successfully.
    This prevents data loss if the new image upload fails.
    """
    if not instance.pk:
        return  # New instance, no old image to delete

    try:
        old_instance = instance.__class__.objects.get(pk=instance.pk)
        old_image = getattr(old_instance, field_name, None)
        new_image = getattr(instance, field_name, None)

        # If the image changed, store the old one for cleanup after save
        if old_image and old_image != new_image:
            if not hasattr(instance, "_old_images_to_cleanup"):
                instance._old_images_to_cleanup = []
            instance._old_images_to_cleanup.append(old_image)
    except instance.__class__.DoesNotExist:
        pass  # Instance doesn't exist yet, nothing to cleanup


def _cleanup_old_images_after_save(instance):
    """
    Delete old images from Cloudinary after new images were saved successfully (post_save).
    Only deletes images that were captured in pre_save.
    """
    if hasattr(instance, "_old_images_to_cleanup"):
        for old_image in instance._old_images_to_cleanup:
            _cleanup_cloudinary_image(old_image)
        delattr(instance, "_old_images_to_cleanup")


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


# =========================
# Image replacement cleanup
# =========================


@receiver(pre_save, sender=Section)
def capture_section_old_image(sender, instance, **kwargs):
    """Capture old image before saving."""
    _capture_old_image_for_cleanup(instance, "image")


@receiver(post_save, sender=Section)
def cleanup_section_old_image(sender, instance, **kwargs):
    """Cleanup old image after new one is saved successfully."""
    _cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=AreaCategory)
def capture_area_category_old_image(sender, instance, **kwargs):
    """Capture old image before saving."""
    _capture_old_image_for_cleanup(instance, "image")


@receiver(post_save, sender=AreaCategory)
def cleanup_area_category_old_image(sender, instance, **kwargs):
    """Cleanup old image after new one is saved successfully."""
    _cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=Area)
def capture_area_old_image(sender, instance, **kwargs):
    """Capture old image before saving."""
    _capture_old_image_for_cleanup(instance, "image")


@receiver(post_save, sender=Area)
def cleanup_area_old_image(sender, instance, **kwargs):
    """Cleanup old image after new one is saved successfully."""
    _cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=Pack)
def capture_pack_old_image(sender, instance, **kwargs):
    """Capture old image before saving."""
    _capture_old_image_for_cleanup(instance, "image")


@receiver(post_save, sender=Pack)
def cleanup_pack_old_image(sender, instance, **kwargs):
    """Cleanup old image after new one is saved successfully."""
    _cleanup_old_images_after_save(instance)


@receiver(pre_save, sender=WaxingContent)
def capture_waxing_content_old_images(sender, instance, **kwargs):
    """Capture old images before saving."""
    _capture_old_image_for_cleanup(instance, "image")
    _capture_old_image_for_cleanup(instance, "benefits_image")
    _capture_old_image_for_cleanup(instance, "recommendations_image")


@receiver(post_save, sender=WaxingContent)
def cleanup_waxing_content_old_images(sender, instance, **kwargs):
    """Cleanup old images after new ones are saved successfully."""
    _cleanup_old_images_after_save(instance)

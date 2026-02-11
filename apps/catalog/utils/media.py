import os

from cloudinary.utils import cloudinary_url

from rest_framework.exceptions import ValidationError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v", ".avi"}


def detect_media_type(file_obj):
    content_type = getattr(file_obj, "content_type", "") or ""
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("image/"):
        return "image"

    name = getattr(file_obj, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return None


def ensure_media_type(file_obj):
    media_type = detect_media_type(file_obj)
    if not media_type:
        raise ValidationError(
            "Formato no soportado. Subí imágenes (jpg, png, webp, gif) o videos (mp4, mov, webm, m4v, avi)."
        )
    return media_type


def build_media_url(file_field, media_type):
    if not file_field:
        return None
    name = getattr(file_field, "name", None)
    if media_type == "video":
        try:
            url, _ = cloudinary_url(
                name,
                resource_type="video",
                secure=True,
            )
            return url
        except Exception:
            pass
    try:
        storage = getattr(file_field, "storage", None)
        if storage and name:
            return storage.url(name)
    except Exception:
        pass
    return getattr(file_field, "url", None)


def build_video_thumbnail_url(file_field, start_offset="auto"):
    if not file_field:
        return None
    name = getattr(file_field, "name", None)
    if not name:
        return None
    try:
        url, _ = cloudinary_url(
            name,
            resource_type="video",
            secure=True,
            format="jpg",
            transformation=[{"start_offset": start_offset}],
        )
        return url
    except Exception:
        return None

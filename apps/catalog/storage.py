from copy import deepcopy
import posixpath
import uuid

from django.conf import settings
import cloudinary.uploader
from cloudinary_storage.storage import MediaCloudinaryStorage

from .utils.media import detect_media_type


class AutoMediaCloudinaryStorage(MediaCloudinaryStorage):
    """
    Fuerza resource_type según el archivo (image/video) para evitar errores
    cuando Cloudinary intenta subir videos como imágenes.
    """

    def _upload(self, name, content):
        options = self._get_upload_options_safe(name, content)

        options["public_id"] = self._build_public_id(name)
        options.pop("use_filename", None)
        options.pop("unique_filename", None)

        media_type = detect_media_type(content)
        if media_type == "video":
            options["resource_type"] = "video"
        elif media_type == "image":
            options["resource_type"] = "image"
        else:
            options["resource_type"] = "auto"

        return cloudinary.uploader.upload(content, **options)

    def _build_public_id(self, name):
        clean_name = (name or "").replace("\\", "/")
        dir_name = posixpath.dirname(clean_name)
        base_name = posixpath.basename(clean_name)
        base_no_ext, _ = posixpath.splitext(base_name)
        suffix = uuid.uuid4().hex[:6]
        if base_no_ext:
            final_name = f"{base_no_ext}-{suffix}"
        else:
            final_name = suffix
        public_id = f"{dir_name}/{final_name}" if dir_name else final_name
        max_len = 255
        if len(public_id) > max_len:
            overflow = len(public_id) - max_len
            if base_no_ext:
                trimmed = base_no_ext[: max(1, len(base_no_ext) - overflow)]
                final_name = f"{trimmed}-{suffix}"
                public_id = (
                    f"{dir_name}/{final_name}" if dir_name else final_name
                )
        return public_id

    def _get_upload_options_safe(self, name, content):
        if hasattr(self, "_get_upload_options"):
            return deepcopy(self._get_upload_options(name, content))
        if hasattr(self, "_get_params"):
            return deepcopy(self._get_params(name, content))
        if hasattr(self, "options"):
            return deepcopy(self.options)
        if hasattr(self, "_options"):
            return deepcopy(self._options)
        return deepcopy(getattr(settings, "CLOUDINARY_STORAGE", {}))

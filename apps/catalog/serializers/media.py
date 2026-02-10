from rest_framework.exceptions import ValidationError

from ..utils.media import ensure_media_type


class MediaUploadMixin:
    def _media_type_for_file(self, file_obj):
        try:
            return ensure_media_type(file_obj)
        except ValidationError as exc:
            raise ValidationError({"uploaded_media": exc.detail})

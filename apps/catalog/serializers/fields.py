import json
import uuid
from rest_framework import serializers

from ..models import Tag


class TagListField(serializers.Field):
    default_error_messages = {
        "not_list": "Tags debe ser una lista.",
        "invalid_item": "Cada tag debe ser un string o UUID.",
        "empty_tag": "Tag vacio.",
        "missing_tag": "Tag no existe: {value}.",
    }

    def to_internal_value(self, data):
        if isinstance(data, str):
            raw = data.strip()
            if not raw:
                return []
            try:
                data = json.loads(raw)
            except ValueError:
                data = [raw]

        if not isinstance(data, (list, tuple)):
            self.fail("not_list")

        tags = []
        for item in data:
            if isinstance(item, dict):
                if "id" in item:
                    item = item["id"]
                elif "name" in item:
                    item = item["name"]
                else:
                    self.fail("invalid_item")

            if isinstance(item, uuid.UUID):
                tag = Tag.objects.filter(id=item).first()
                if not tag:
                    self.fail("missing_tag", value=item)
                tags.append(tag)
                continue

            if not isinstance(item, str):
                self.fail("invalid_item")

            value = item.strip()
            if not value:
                self.fail("empty_tag")

            try:
                tag_id = uuid.UUID(value)
            except ValueError:
                tag_id = None

            if tag_id:
                tag = Tag.objects.filter(id=tag_id).first()
                if not tag:
                    self.fail("missing_tag", value=tag_id)
            else:
                tag, _ = Tag.objects.get_or_create(name=value)
            tags.append(tag)

        return tags

    def to_representation(self, value):
        if hasattr(value, "all"):
            return [str(tag.id) for tag in value.all()]
        return [str(tag.id) for tag in value]

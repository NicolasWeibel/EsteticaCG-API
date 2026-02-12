import json


def clean_uploaded_media(raw):
    if raw is None:
        return None
    if hasattr(raw, "read"):
        return [raw]
    if isinstance(raw, str):
        return []
    if isinstance(raw, (list, tuple)):
        return [item for item in raw if hasattr(item, "read")]
    return []


def parse_json_list(raw, field_name, error_cls):
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception as exc:
            raise error_cls({field_name: f"JSON inválido: {exc}"})
    if hasattr(raw, "read"):
        try:
            content = raw.read()
            if hasattr(raw, "seek"):
                raw.seek(0)
            return json.loads(content)
        except Exception as exc:
            raise error_cls({field_name: f"JSON inválido: {exc}"})
    return raw

def is_inline_deleted(value):
    return str(value).lower() in {"1", "true", "on", "yes"}


def get_formset_total(data, prefix):
    try:
        return int(data.get(f"{prefix}-TOTAL_FORMS", 0))
    except (TypeError, ValueError):
        return 0

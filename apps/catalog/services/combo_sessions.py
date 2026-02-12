def prune_session_items_for_sessions(combo, sessions=None):
    target_sessions = combo.sessions if sessions is None else sessions
    target_sessions = target_sessions or 0

    if target_sessions <= 0:
        deleted_count, _ = combo.session_items.all().delete()
        return deleted_count

    deleted_count, _ = combo.session_items.filter(
        session_index__gt=target_sessions
    ).delete()
    return deleted_count


def serialize_session_items_for_validation(items):
    return [
        {"session_index": item.session_index, "ingredient": item.ingredient_id}
        for item in items
    ]

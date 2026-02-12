from django.core.exceptions import ValidationError as DjangoValidationError


def validate_treatment_rules(
    *,
    is_active,
    requires_zones,
    has_zones,
    error_cls=DjangoValidationError,
):
    if not is_active:
        return
    if has_zones:
        return
    if requires_zones:
        raise error_cls(
            {
                "zone_configs": "Este tratamiento requiere al menos una zona configurada."
            }
        )
    raise error_cls(
        {"zone_configs": "Un tratamiento activo requiere al menos una zona configurada."}
    )


def validate_combo_rules(
    *,
    is_active,
    sessions,
    ingredient_ids,
    session_items,
    error_cls=DjangoValidationError,
):
    total_sessions = sessions or 0
    ingredients_set = {
        str(item_id) for item_id in (ingredient_ids or [])
    }

    if total_sessions == 0:
        if is_active:
            raise error_cls(
                {"sessions": "sessions no puede ser 0 si el combo está activo."}
            )
        if session_items:
            raise error_cls(
                {"session_items": "session_items no es válido si sessions es 0."}
            )
        return

    if session_items is None:
        raise error_cls({"session_items": "session_items es requerido."})

    if not ingredients_set:
        raise error_cls(
            {"ingredients": "El combo debe tener al menos un ingrediente."}
        )

    session_counts = {i: 0 for i in range(1, total_sessions + 1)}
    used_ingredients = set()
    seen_pairs = set()

    for item in session_items:
        session_index = item.get("session_index")
        ingredient_id = str(item.get("ingredient"))

        if session_index not in session_counts:
            raise error_cls(
                {"session_items": f"session_index inválido: {session_index}."}
            )
        if ingredient_id not in ingredients_set:
            raise error_cls(
                {"session_items": "El ingrediente no pertenece al combo."}
            )

        pair_key = (session_index, ingredient_id)
        if pair_key in seen_pairs:
            raise error_cls(
                {
                    "session_items": "No se permiten ingredientes repetidos en la misma sesión."
                }
            )
        seen_pairs.add(pair_key)
        session_counts[session_index] += 1
        used_ingredients.add(ingredient_id)

    empty_sessions = [
        idx for idx, count in session_counts.items() if count == 0
    ]
    if empty_sessions:
        raise error_cls(
            {
                "session_items": (
                    f"Las sesiones sin ingredientes no están permitidas: {empty_sessions}."
                )
            }
        )

    missing_ingredients = sorted(
        ingredients_set.difference(used_ingredients)
    )
    if missing_ingredients:
        raise error_cls(
            {"session_items": "Cada ingrediente debe estar en al menos una sesión."}
        )

from django.contrib import admin
from django.db.models import Q
from ..models import TreatmentZoneIncompatibility, TreatmentZoneConfig


def _overlap_filter_for_position(pos: str) -> Q:
    """
    Devuelve un filtro Q para limitar por solape de body_position.
    - 'boca-arriba'  → incluye ['boca-arriba', 'any']
    - 'boca-abajo'   → incluye ['boca-abajo',  'any']
    - 'any'          → sin filtro (solapa con todo)
    """
    if pos == "boca-arriba":
        return Q(body_position__in=["boca-arriba", "any"])
    elif pos == "boca-abajo":
        return Q(body_position__in=["boca-abajo", "any"])
    return Q()  # any → no se filtra


def _current_tzc_from_admin_request(request):
    """
    Intenta obtener el TZC actual desde la URL del admin (change view).
    Si no hay object_id (por ejemplo en add), devuelve None.
    """
    obj_id = getattr(getattr(request, "resolver_match", None), "kwargs", {}).get(
        "object_id"
    )
    if not obj_id:
        return None
    try:
        return TreatmentZoneConfig.objects.select_related(
            "treatment", "treatment__category", "zone"
        ).get(pk=obj_id)
    except TreatmentZoneConfig.DoesNotExist:
        return None


def _compatible_tzc_queryset_for(current: TreatmentZoneConfig):
    """
    Construye el queryset base de TZCs compatibles:
    - misma categoría
    - zona distinta
    - body_position solapada
    - ordenado por nombre de zona (y después por título de tratamiento)
    """
    qs = (
        TreatmentZoneConfig.objects.select_related(
            "treatment", "treatment__category", "zone"
        )
        .exclude(zone_id=current.zone_id)
        .filter(treatment__category_id=current.treatment.category_id)
    )

    # aplicar solape de posición
    qs = qs.filter(_overlap_filter_for_position(current.body_position))
    # ordenar por zona y luego tratamiento (más legible en el widget)
    qs = qs.order_by("zone__name", "treatment__title")
    return qs


def _exclude_already_linked(qs, current: TreatmentZoneConfig):
    """
    Excluye del queryset los TZC que ya estén ligados en incompatibilidades
    con el 'current' (sea como left o como right), y también excluye al propio current.
    """
    already_left_ids = TreatmentZoneIncompatibility.objects.filter(
        left_tzc=current
    ).values_list("right_tzc_id", flat=True)

    already_right_ids = TreatmentZoneIncompatibility.objects.filter(
        right_tzc=current
    ).values_list("left_tzc_id", flat=True)

    return qs.exclude(
        Q(pk=current.pk) | Q(pk__in=already_left_ids) | Q(pk__in=already_right_ids)
    )


class IncompatibilityInline(admin.TabularInline):
    """
    Inline donde este TZC aparece como 'left'; el FK editable es 'right_tzc'.
    Filtramos el queryset de 'right_tzc' para:
      - misma categoría
      - zona distinta
      - body_position que solape (any o igual)
      - excluir los ya elegidos (en left o right)
      - ordenar por zone__name
    """

    model = TreatmentZoneIncompatibility
    fk_name = "left_tzc"
    extra = 0
    autocomplete_fields = ("right_tzc",)
    verbose_name = "Incompatibilidad (este TZC como izquierda)"
    verbose_name_plural = "Incompatibilidades donde este TZC está a la izquierda"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "right_tzc":
            current = _current_tzc_from_admin_request(request)
            if current is not None:
                qs = _compatible_tzc_queryset_for(current)
                qs = _exclude_already_linked(qs, current)
                field.queryset = qs
        return field


class IncompatibilityInlineReverse(IncompatibilityInline):
    """
    Inline espejo donde este TZC aparece como 'right'; el FK editable es 'left_tzc'.
    Se aplica el mismo filtrado/ordenamiento que en el inline anterior.
    """

    fk_name = "right_tzc"
    verbose_name = "Incompatibilidad (este TZC como derecha)"
    verbose_name_plural = "Incompatibilidades donde este TZC está a la derecha"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super(IncompatibilityInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )  # noqa
        if db_field.name == "left_tzc":
            current = _current_tzc_from_admin_request(request)
            if current is not None:
                qs = _compatible_tzc_queryset_for(current)
                qs = _exclude_already_linked(qs, current)
                field.queryset = qs
        return field


@admin.register(TreatmentZoneIncompatibility)
class TreatmentZoneIncompatibilityAdmin(admin.ModelAdmin):
    list_display = ("left_tzc", "right_tzc", "created_at")
    search_fields = (
        "left_tzc__treatment__title",
        "right_tzc__treatment__title",
        "left_tzc__zone__name",
        "right_tzc__zone__name",
    )
    autocomplete_fields = ("left_tzc", "right_tzc")

    def _get_current_object(self, request):
        from apps.catalog.models import TreatmentZoneIncompatibility

        object_id = request.resolver_match.kwargs.get("object_id")
        if object_id:
            try:
                return TreatmentZoneIncompatibility.objects.get(pk=object_id)
            except TreatmentZoneIncompatibility.DoesNotExist:
                return None
        return None

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        current_obj = self._get_current_object(request)

        # Si estamos completando 'right_tzc' o 'left_tzc'
        if db_field.name in {"left_tzc", "right_tzc"}:
            other_field = "right_tzc" if db_field.name == "left_tzc" else "left_tzc"
            other_value = getattr(current_obj, other_field, None)

            # Aplicamos filtro base de compatibilidad con el otro extremo
            if other_value:
                qs = _compatible_tzc_queryset_for(other_value)
                qs = _exclude_already_linked(qs, other_value)
            else:
                # Si no hay otro extremo, mostramos solo los posibles candidatos
                # (que podrían ser parte de incompatibilidad futura)
                qs = TreatmentZoneConfig.objects.filter(
                    body_position__in=["boca-arriba", "boca-abajo", "any"]
                )

            # Siempre excluímos el ya seleccionado para evitar auto-incompatibilidad
            if current_obj and db_field.name == "left_tzc" and current_obj.right_tzc_id:
                qs = qs.exclude(id=current_obj.right_tzc_id)
            if current_obj and db_field.name == "right_tzc" and current_obj.left_tzc_id:
                qs = qs.exclude(id=current_obj.left_tzc_id)

            field.queryset = qs.order_by("zone__name", "treatment__title")

        return field

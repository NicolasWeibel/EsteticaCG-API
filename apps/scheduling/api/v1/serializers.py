from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import Journey


def _validate_time_slots(time_slots):
    if not time_slots:
        raise serializers.ValidationError("Se requiere al menos un horario.")
    ordered = sorted(time_slots, key=lambda slot: slot["start"])
    for prev_slot, next_slot in zip(ordered, ordered[1:]):
        if prev_slot["end"] > next_slot["start"]:
            raise serializers.ValidationError("Los horarios se solapan.")
    return time_slots


class TimeSlotSerializer(serializers.Serializer):
    start = serializers.TimeField()
    end = serializers.TimeField()

    def validate(self, attrs):
        if attrs["start"] >= attrs["end"]:
            raise serializers.ValidationError(
                {"end": "La hora de fin debe ser mayor que la de inicio."}
            )
        return attrs


class DateRangeSerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()


class WeeklyConfigSerializer(serializers.Serializer):
    day_of_week = serializers.IntegerField(min_value=1, max_value=7)
    time_slots = TimeSlotSerializer(many=True, allow_empty=False)

    def validate_time_slots(self, value):
        return _validate_time_slots(value)


class RecurrenceRuleSerializer(serializers.Serializer):
    MODE_SPECIFIC = "SPECIFIC_DATE"
    MODE_RELATIVE = "RELATIVE"

    mode = serializers.ChoiceField(choices=(MODE_SPECIFIC, MODE_RELATIVE))
    day_of_month = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=31
    )
    week_day = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=7
    )
    index = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)

    def validate(self, attrs):
        mode = attrs.get("mode")
        if mode == self.MODE_SPECIFIC:
            if not attrs.get("day_of_month"):
                raise serializers.ValidationError(
                    {"day_of_month": "Se requiere day_of_month para SPECIFIC_DATE."}
                )
            if attrs.get("week_day") or attrs.get("index"):
                raise serializers.ValidationError(
                    "week_day e index no aplican para SPECIFIC_DATE."
                )
        else:
            if not attrs.get("week_day") or not attrs.get("index"):
                raise serializers.ValidationError(
                    "Se requieren week_day e index para RELATIVE."
                )
            if attrs.get("day_of_month"):
                raise serializers.ValidationError(
                    "day_of_month no aplica para RELATIVE."
                )
        return attrs


class AvailabilityCreateSerializer(serializers.Serializer):
    TYPE_WEEKLY = "WEEKLY"
    TYPE_MONTHLY = "MONTHLY"
    TYPE_SINGLE = "SINGLE"

    type = serializers.ChoiceField(choices=(TYPE_WEEKLY, TYPE_MONTHLY, TYPE_SINGLE))
    jornada_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )
    date_range = DateRangeSerializer()
    weekly_config = WeeklyConfigSerializer(many=True, required=False)
    recurrence_rule = RecurrenceRuleSerializer(required=False)
    time_slots = TimeSlotSerializer(many=True, required=False, allow_empty=False)

    def validate_jornada_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        found_ids = set(
            Journey.objects.filter(id__in=unique_ids).values_list("id", flat=True)
        )
        missing = [str(item) for item in unique_ids if item not in found_ids]
        if missing:
            raise serializers.ValidationError(
                f"Jornadas no encontradas: {', '.join(missing)}"
            )
        return unique_ids

    def validate(self, attrs):
        date_range = attrs["date_range"]
        if date_range["start"] > date_range["end"]:
            raise serializers.ValidationError(
                {"date_range": "La fecha inicio no puede ser mayor a la fecha fin."}
            )
        today = timezone.localdate()
        if date_range["start"] < today:
            raise serializers.ValidationError(
                {"date_range": "La fecha inicio no puede ser anterior a hoy."}
            )

        availability_type = attrs["type"]
        weekly_config = attrs.get("weekly_config")
        recurrence_rule = attrs.get("recurrence_rule")
        time_slots = attrs.get("time_slots")

        if availability_type == self.TYPE_WEEKLY:
            if not weekly_config:
                raise serializers.ValidationError(
                    {"weekly_config": "weekly_config es requerido para WEEKLY."}
                )
            if time_slots is not None:
                raise serializers.ValidationError(
                    {"time_slots": "time_slots no aplica para WEEKLY."}
                )
            if recurrence_rule is not None:
                raise serializers.ValidationError(
                    {"recurrence_rule": "recurrence_rule no aplica para WEEKLY."}
                )
            seen_days = set()
            for item in weekly_config:
                day = item["day_of_week"]
                if day in seen_days:
                    raise serializers.ValidationError(
                        {"weekly_config": "day_of_week duplicado en weekly_config."}
                    )
                seen_days.add(day)
        elif availability_type == self.TYPE_MONTHLY:
            if recurrence_rule is None:
                raise serializers.ValidationError(
                    {"recurrence_rule": "recurrence_rule es requerido para MONTHLY."}
                )
            if not time_slots:
                raise serializers.ValidationError(
                    {"time_slots": "time_slots es requerido para MONTHLY."}
                )
            if weekly_config is not None:
                raise serializers.ValidationError(
                    {"weekly_config": "weekly_config no aplica para MONTHLY."}
                )
            _validate_time_slots(time_slots)
        elif availability_type == self.TYPE_SINGLE:
            if date_range["start"] != date_range["end"]:
                raise serializers.ValidationError(
                    {"date_range": "Para SINGLE, start y end deben ser iguales."}
                )
            if not time_slots:
                raise serializers.ValidationError(
                    {"time_slots": "time_slots es requerido para SINGLE."}
                )
            if weekly_config is not None or recurrence_rule is not None:
                raise serializers.ValidationError(
                    "weekly_config y recurrence_rule no aplican para SINGLE."
                )
            _validate_time_slots(time_slots)

        return attrs


class AvailabilityBatchUpdateSerializer(serializers.Serializer):
    TYPE_WEEKLY = "WEEKLY"
    TYPE_MONTHLY = "MONTHLY"
    TYPE_SINGLE = "SINGLE"

    type = serializers.ChoiceField(choices=(TYPE_WEEKLY, TYPE_MONTHLY, TYPE_SINGLE))
    jornada_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False
    )
    date_range = DateRangeSerializer()
    weekly_config = WeeklyConfigSerializer(many=True, required=False)
    recurrence_rule = RecurrenceRuleSerializer(required=False)
    time_slots = TimeSlotSerializer(many=True, required=False, allow_empty=False)
    effective_from = serializers.DateField(required=False, allow_null=True)

    def validate_jornada_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        found_ids = set(
            Journey.objects.filter(id__in=unique_ids).values_list("id", flat=True)
        )
        missing = [str(item) for item in unique_ids if item not in found_ids]
        if missing:
            raise serializers.ValidationError(
                f"Jornadas no encontradas: {', '.join(missing)}"
            )
        return unique_ids

    def validate(self, attrs):
        date_range = attrs["date_range"]
        if date_range["start"] > date_range["end"]:
            raise serializers.ValidationError(
                {"date_range": "La fecha inicio no puede ser mayor a la fecha fin."}
            )
        effective_from = attrs.get("effective_from")
        if effective_from and effective_from < timezone.localdate():
            raise serializers.ValidationError(
                {"effective_from": "effective_from no puede ser anterior a hoy."}
            )
        if effective_from and effective_from > date_range["end"]:
            raise serializers.ValidationError(
                {"effective_from": "effective_from no puede ser mayor que date_range.end."}
            )

        availability_type = attrs["type"]
        weekly_config = attrs.get("weekly_config")
        recurrence_rule = attrs.get("recurrence_rule")
        time_slots = attrs.get("time_slots")

        if availability_type == self.TYPE_WEEKLY:
            if not weekly_config:
                raise serializers.ValidationError(
                    {"weekly_config": "weekly_config es requerido para WEEKLY."}
                )
            if time_slots is not None:
                raise serializers.ValidationError(
                    {"time_slots": "time_slots no aplica para WEEKLY."}
                )
            if recurrence_rule is not None:
                raise serializers.ValidationError(
                    {"recurrence_rule": "recurrence_rule no aplica para WEEKLY."}
                )
            seen_days = set()
            for item in weekly_config:
                day = item["day_of_week"]
                if day in seen_days:
                    raise serializers.ValidationError(
                        {"weekly_config": "day_of_week duplicado en weekly_config."}
                    )
                seen_days.add(day)
        elif availability_type == self.TYPE_MONTHLY:
            if recurrence_rule is None:
                raise serializers.ValidationError(
                    {"recurrence_rule": "recurrence_rule es requerido para MONTHLY."}
                )
            if not time_slots:
                raise serializers.ValidationError(
                    {"time_slots": "time_slots es requerido para MONTHLY."}
                )
            if weekly_config is not None:
                raise serializers.ValidationError(
                    {"weekly_config": "weekly_config no aplica para MONTHLY."}
                )
            _validate_time_slots(time_slots)
        elif availability_type == self.TYPE_SINGLE:
            if date_range["start"] != date_range["end"]:
                raise serializers.ValidationError(
                    {"date_range": "Para SINGLE, start y end deben ser iguales."}
                )
            if not time_slots:
                raise serializers.ValidationError(
                    {"time_slots": "time_slots es requerido para SINGLE."}
                )
            if weekly_config is not None or recurrence_rule is not None:
                raise serializers.ValidationError(
                    "weekly_config y recurrence_rule no aplican para SINGLE."
                )
            _validate_time_slots(time_slots)

        return attrs


class AvailabilityBatchSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    type = serializers.CharField()
    date_start = serializers.DateField()
    date_end = serializers.DateField()
    rule = serializers.JSONField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ScheduleBlockCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    jornada_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, required=False
    )
    time_slot = TimeSlotSerializer()
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    all_jornadas = serializers.BooleanField(required=False, default=False)

    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError(
                "La fecha no puede ser anterior a hoy."
            )
        return value

    def validate_jornada_ids(self, value):
        unique_ids = list(dict.fromkeys(value))
        found_ids = set(
            Journey.objects.filter(id__in=unique_ids).values_list("id", flat=True)
        )
        missing = [str(item) for item in unique_ids if item not in found_ids]
        if missing:
            raise serializers.ValidationError(
                f"Jornadas no encontradas: {', '.join(missing)}"
            )
        return unique_ids

    def validate(self, attrs):
        all_jornadas = attrs.get("all_jornadas", False)
        jornada_ids = attrs.get("jornada_ids")
        if all_jornadas and jornada_ids:
            raise serializers.ValidationError(
                {"jornada_ids": "No enviar jornada_ids cuando all_jornadas=true."}
            )
        if not all_jornadas and not jornada_ids:
            raise serializers.ValidationError(
                {"jornada_ids": "jornada_ids es requerido si all_jornadas es false."}
            )
        return attrs


class AvailabilityListQuerySerializer(serializers.Serializer):
    jornada_id = serializers.UUIDField(required=False)
    batch_id = serializers.UUIDField(required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)

    def validate(self, attrs):
        has_jornada = bool(attrs.get("jornada_id"))
        has_batch = bool(attrs.get("batch_id"))
        if not has_jornada and not has_batch:
            raise serializers.ValidationError(
                "Se requiere jornada_id o batch_id."
            )
        start = attrs.get("start")
        end = attrs.get("end")
        if (start and not end) or (end and not start):
            raise serializers.ValidationError(
                {"date_range": "start y end deben enviarse juntos."}
            )
        if start and end and start > end:
            raise serializers.ValidationError(
                {"date_range": "start no puede ser mayor que end."}
            )
        return attrs


class AvailabilityDeleteQuerySerializer(serializers.Serializer):
    jornada_id = serializers.UUIDField(required=False)
    batch_id = serializers.UUIDField(required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)

    def validate(self, attrs):
        has_jornada = bool(attrs.get("jornada_id"))
        has_batch = bool(attrs.get("batch_id"))
        if not has_jornada and not has_batch:
            raise serializers.ValidationError(
                "Se requiere jornada_id o batch_id."
            )
        start = attrs.get("start")
        end = attrs.get("end")
        if (start and not end) or (end and not start):
            raise serializers.ValidationError(
                {"date_range": "start y end deben enviarse juntos."}
            )
        if start and end and start > end:
            raise serializers.ValidationError(
                {"date_range": "start no puede ser mayor que end."}
            )
        return attrs


class ScheduleBlockListQuerySerializer(serializers.Serializer):
    jornada_id = serializers.UUIDField(required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)

    def validate(self, attrs):
        has_jornada = bool(attrs.get("jornada_id"))
        start = attrs.get("start")
        end = attrs.get("end")
        if not has_jornada and not (start and end):
            raise serializers.ValidationError(
                "Se requiere jornada_id o date_range."
            )
        if (start and not end) or (end and not start):
            raise serializers.ValidationError(
                {"date_range": "start y end deben enviarse juntos."}
            )
        if start and end and start > end:
            raise serializers.ValidationError(
                {"date_range": "start no puede ser mayor que end."}
            )
        return attrs


class ScheduleBlockDeleteQuerySerializer(serializers.Serializer):
    jornada_id = serializers.UUIDField(required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)

    def validate(self, attrs):
        has_jornada = bool(attrs.get("jornada_id"))
        start = attrs.get("start")
        end = attrs.get("end")
        if not has_jornada and not (start and end):
            raise serializers.ValidationError(
                "Se requiere jornada_id o date_range."
            )
        if (start and not end) or (end and not start):
            raise serializers.ValidationError(
                {"date_range": "start y end deben enviarse juntos."}
            )
        if start and end and start > end:
            raise serializers.ValidationError(
                {"date_range": "start no puede ser mayor que end."}
            )
        return attrs

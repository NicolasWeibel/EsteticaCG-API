import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Journey
from apps.scheduling.models import (
    AvailabilityBatch,
    AvailabilityDay,
    AvailabilitySlot,
    ScheduleBlock,
)


class AvailabilityConflictError(Exception):
    def __init__(self, journey_name, date):
        date_str = date.strftime("%d/%m/%Y") if hasattr(date, "strftime") else str(date)
        super().__init__(
            f"Error: La jornada {journey_name} ya tiene un horario asignado el dia {date_str} que se solapa con el intento de carga."
        )
        self.journey_name = journey_name
        self.date = date


class EmptyAvailabilityError(Exception):
    pass


def _date_range(start_date, end_date) -> Iterable:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _is_nth_weekday(target_date, week_day: int, index: int) -> bool:
    if target_date.isoweekday() != week_day:
        return False
    first_day = target_date.replace(day=1)
    first_weekday = first_day.isoweekday()
    day_offset = (week_day - first_weekday) % 7
    first_occurrence_day = 1 + day_offset
    if target_date.day < first_occurrence_day:
        return False
    occurrence = 1 + ((target_date.day - first_occurrence_day) // 7)
    return occurrence == index


def _check_conflicts(intervals, journey_map, exclude_batch_id=None) -> None:
    for interval in intervals:
        qs = AvailabilitySlot.objects.filter(
            availability_day__journey_id=interval["journey_id"],
            availability_day__date=interval["date"],
            start_time__lt=interval["end_time"],
            end_time__gt=interval["start_time"],
        )
        if exclude_batch_id:
            qs = qs.exclude(availability_day__batch_id=exclude_batch_id)
        if qs.exists():
            journey_name = journey_map.get(interval["journey_id"]) or interval["journey_id"]
            raise AvailabilityConflictError(
                journey_name=journey_name, date=interval["date"]
            )


def _serialize_rule_payload(payload: dict) -> dict:
    date_range = payload["date_range"]
    rule = {
        "type": payload["type"],
        "jornada_ids": [str(jid) for jid in payload["jornada_ids"]],
        "date_range": {
            "start": date_range["start"].isoformat(),
            "end": date_range["end"].isoformat(),
        },
    }
    if payload.get("weekly_config"):
        rule["weekly_config"] = [
            {
                "day_of_week": item["day_of_week"],
                "time_slots": [
                    {
                        "start": slot["start"].strftime("%H:%M"),
                        "end": slot["end"].strftime("%H:%M"),
                    }
                    for slot in item["time_slots"]
                ],
            }
            for item in payload["weekly_config"]
        ]
    if payload.get("recurrence_rule"):
        rule["recurrence_rule"] = payload["recurrence_rule"]
    if payload.get("time_slots"):
        rule["time_slots"] = [
            {
                "start": slot["start"].strftime("%H:%M"),
                "end": slot["end"].strftime("%H:%M"),
            }
            for slot in payload["time_slots"]
        ]
    return rule


def _build_intervals(*, payload: dict, start_date=None, end_date=None) -> list[dict]:
    availability_type = payload["type"]
    journey_ids = payload["jornada_ids"]
    date_range = payload["date_range"]
    start_date = start_date or date_range["start"]
    end_date = end_date or date_range["end"]
    weekly_config = payload.get("weekly_config") or []
    recurrence_rule = payload.get("recurrence_rule") or {}
    time_slots = payload.get("time_slots") or []

    weekly_map = {item["day_of_week"]: item["time_slots"] for item in weekly_config}
    intervals = []

    for journey_id in journey_ids:
        for current_date in _date_range(start_date, end_date):
            slots_for_day = []
            if availability_type == "WEEKLY":
                slots_for_day = weekly_map.get(current_date.isoweekday(), [])
            elif availability_type == "MONTHLY":
                mode = recurrence_rule.get("mode")
                if mode == "SPECIFIC_DATE":
                    if current_date.day == recurrence_rule.get("day_of_month"):
                        slots_for_day = time_slots
                elif mode == "RELATIVE":
                    if _is_nth_weekday(
                        current_date,
                        recurrence_rule.get("week_day"),
                        recurrence_rule.get("index"),
                    ):
                        slots_for_day = time_slots
            elif availability_type == "SINGLE":
                slots_for_day = time_slots

            if not slots_for_day:
                continue

            for slot in slots_for_day:
                intervals.append(
                    {
                        "journey_id": journey_id,
                        "date": current_date,
                        "start_time": slot["start"],
                        "end_time": slot["end"],
                    }
                )

    return intervals


def create_availability(*, payload: dict) -> dict:
    batch_id = uuid.uuid4()
    intervals = _build_intervals(payload=payload)

    if not intervals:
        raise EmptyAvailabilityError("No se generaron horarios para el rango indicado.")

    journey_ids = payload["jornada_ids"]
    date_range = payload["date_range"]
    start_date = date_range["start"]
    end_date = date_range["end"]
    rule_payload = _serialize_rule_payload(payload)
    journey_map = {
        journey.id: journey.title
        for journey in Journey.objects.filter(id__in=journey_ids).only("id", "title")
    }

    with transaction.atomic():
        _check_conflicts(intervals, journey_map)
        AvailabilityBatch.objects.create(
            id=batch_id,
            type=payload["type"],
            date_start=start_date,
            date_end=end_date,
            rule=rule_payload,
        )
        day_map = {}
        slot_rows = []
        for interval in intervals:
            key = (interval["journey_id"], interval["date"])
            if key not in day_map:
                day_map[key] = AvailabilityDay.objects.create(
                    journey_id=interval["journey_id"],
                    date=interval["date"],
                    batch_id=batch_id,
                )
            slot_rows.append(
                AvailabilitySlot(
                    availability_day=day_map[key],
                    start_time=interval["start_time"],
                    end_time=interval["end_time"],
                )
            )
        AvailabilitySlot.objects.bulk_create(slot_rows)

    return {
        "batch_id": str(batch_id),
        "days_created": len(day_map),
        "slots_created": len(slot_rows),
    }


def create_blocks(*, payload: dict) -> dict:
    all_jornadas = payload.get("all_jornadas", False)
    journey_ids = payload.get("jornada_ids") or []
    block_date = payload["date"]
    time_slot = payload["time_slot"]
    reason = payload.get("reason")

    if all_jornadas:
        journey_ids = list(Journey.objects.values_list("id", flat=True))
    if not journey_ids:
        raise ValueError("No hay jornadas para bloquear.")

    blocks = [
        ScheduleBlock(
            journey_id=journey_id,
            date=block_date,
            start_time=time_slot["start"],
            end_time=time_slot["end"],
            reason=reason,
        )
        for journey_id in journey_ids
    ]
    ScheduleBlock.objects.bulk_create(blocks)

    return {"blocks_created": len(blocks)}


def update_availability_batch(*, batch_id, payload: dict) -> dict:
    batch = AvailabilityBatch.objects.filter(id=batch_id).first()
    if not batch:
        raise AvailabilityBatch.DoesNotExist

    journey_ids = payload["jornada_ids"]
    date_range = payload["date_range"]
    start_date = date_range["start"]
    end_date = date_range["end"]
    effective_from = payload.get("effective_from") or timezone.localdate()
    effective_start = max(start_date, effective_from)

    intervals = []
    if effective_start <= end_date:
        intervals = _build_intervals(
            payload=payload, start_date=effective_start, end_date=end_date
        )

    new_set = {
        (
            interval["journey_id"],
            interval["date"],
            interval["start_time"],
            interval["end_time"],
        )
        for interval in intervals
    }

    days_qs = AvailabilityDay.objects.filter(
        batch_id=batch_id, date__gte=effective_start
    )
    day_map = {(day.journey_id, day.date): day for day in days_qs}
    slots_qs = AvailabilitySlot.objects.filter(availability_day__in=days_qs)

    old_set = set()
    slot_map = {}
    old_day_counts = defaultdict(int)
    for slot in slots_qs:
        key = (
            slot.availability_day.journey_id,
            slot.availability_day.date,
            slot.start_time,
            slot.end_time,
        )
        old_set.add(key)
        slot_map[key] = slot.id
        old_day_counts[(key[0], key[1])] += 1

    to_add = new_set - old_set
    to_delete = old_set - new_set

    journey_map = {
        journey.id: journey.title
        for journey in Journey.objects.filter(id__in=journey_ids).only("id", "title")
    }
    if to_add:
        _check_conflicts(
            [
                {
                    "journey_id": item[0],
                    "date": item[1],
                    "start_time": item[2],
                    "end_time": item[3],
                }
                for item in to_add
            ],
            journey_map,
            exclude_batch_id=batch_id,
        )

    removed_by_day = defaultdict(int)
    for item in to_delete:
        removed_by_day[(item[0], item[1])] += 1
    added_by_day = defaultdict(int)
    for item in to_add:
        added_by_day[(item[0], item[1])] += 1

    days_to_delete = []
    for day_key, old_count in old_day_counts.items():
        final_count = old_count - removed_by_day[day_key] + added_by_day[day_key]
        if final_count <= 0:
            day = day_map.get(day_key)
            if day:
                days_to_delete.append(day)

    changes_map = defaultdict(lambda: {"added": [], "removed": []})
    for item in to_add:
        changes_map[(item[0], item[1])]["added"].append(
            {"start": item[2].strftime("%H:%M"), "end": item[3].strftime("%H:%M")}
        )
    for item in to_delete:
        changes_map[(item[0], item[1])]["removed"].append(
            {"start": item[2].strftime("%H:%M"), "end": item[3].strftime("%H:%M")}
        )

    with transaction.atomic():
        batch = AvailabilityBatch.objects.select_for_update().get(id=batch_id)
        if to_delete:
            slot_ids = [slot_map[item] for item in to_delete if item in slot_map]
            AvailabilitySlot.objects.filter(id__in=slot_ids).delete()
        if days_to_delete:
            AvailabilityDay.objects.filter(id__in=[day.id for day in days_to_delete]).delete()

        days_created = 0
        slot_rows = []
        for journey_id, date, start_time, end_time in to_add:
            day_key = (journey_id, date)
            day = day_map.get(day_key)
            if not day:
                day = AvailabilityDay.objects.create(
                    journey_id=journey_id,
                    date=date,
                    batch_id=batch_id,
                )
                day_map[day_key] = day
                days_created += 1
            slot_rows.append(
                AvailabilitySlot(
                    availability_day=day,
                    start_time=start_time,
                    end_time=end_time,
                )
            )
        if slot_rows:
            AvailabilitySlot.objects.bulk_create(slot_rows)

        batch.type = payload["type"]
        batch.date_start = start_date
        batch.date_end = end_date
        batch.rule = _serialize_rule_payload(payload)
        batch.save(update_fields=["type", "date_start", "date_end", "rule", "updated_at"])

    changes = []
    if changes_map:
        journey_names = {
            journey.id: journey.title
            for journey in Journey.objects.filter(
                id__in={key[0] for key in changes_map.keys()}
            ).only("id", "title")
        }
        for (journey_id, date), payload_changes in changes_map.items():
            changes.append(
                {
                    "journey_id": str(journey_id),
                    "journey_name": journey_names.get(journey_id, str(journey_id)),
                    "date": date.isoformat(),
                    "added": payload_changes["added"],
                    "removed": payload_changes["removed"],
                }
            )

    return {
        "batch_id": str(batch_id),
        "days_created": days_created,
        "days_deleted": len(days_to_delete),
        "slots_created": len(to_add),
        "slots_deleted": len(to_delete),
        "changes": changes,
    }


def list_availability(*, filters: dict) -> list[dict]:
    qs = AvailabilityDay.objects.select_related("journey").prefetch_related("slots")
    jornada_id = filters.get("jornada_id")
    batch_id = filters.get("batch_id")
    start = filters.get("start")
    end = filters.get("end")

    if jornada_id:
        qs = qs.filter(journey_id=jornada_id)
    if batch_id:
        qs = qs.filter(batch_id=batch_id)
    if start and end:
        qs = qs.filter(date__range=(start, end))

    results = []
    for day in qs.order_by("date", "journey_id"):
        slots = [
            {
                "start": slot.start_time.strftime("%H:%M"),
                "end": slot.end_time.strftime("%H:%M"),
            }
            for slot in day.slots.all().order_by("start_time")
        ]
        results.append(
            {
                "journey_id": str(day.journey_id),
                "journey_name": day.journey.title,
                "date": day.date.isoformat(),
                "batch_id": str(day.batch_id),
                "slots": slots,
            }
        )
    return results


def delete_availability(*, filters: dict) -> dict:
    qs = AvailabilityDay.objects.all()
    jornada_id = filters.get("jornada_id")
    batch_id = filters.get("batch_id")
    start = filters.get("start")
    end = filters.get("end")

    if jornada_id:
        qs = qs.filter(journey_id=jornada_id)
    if batch_id:
        qs = qs.filter(batch_id=batch_id)
    if start and end:
        qs = qs.filter(date__range=(start, end))

    slots_qs = AvailabilitySlot.objects.filter(availability_day__in=qs)
    slots_deleted = slots_qs.count()
    days_deleted = qs.count()
    qs.delete()

    return {"days_deleted": days_deleted, "slots_deleted": slots_deleted}


def list_blocks(*, filters: dict) -> list[dict]:
    qs = ScheduleBlock.objects.select_related("journey")
    jornada_id = filters.get("jornada_id")
    start = filters.get("start")
    end = filters.get("end")

    if jornada_id:
        qs = qs.filter(journey_id=jornada_id)
    if start and end:
        qs = qs.filter(date__range=(start, end))

    results = []
    for block in qs.order_by("date", "journey_id", "start_time"):
        results.append(
            {
                "journey_id": str(block.journey_id),
                "journey_name": block.journey.title,
                "date": block.date.isoformat(),
                "start": block.start_time.strftime("%H:%M"),
                "end": block.end_time.strftime("%H:%M"),
                "reason": block.reason,
            }
        )
    return results


def delete_blocks(*, filters: dict) -> dict:
    qs = ScheduleBlock.objects.all()
    jornada_id = filters.get("jornada_id")
    start = filters.get("start")
    end = filters.get("end")

    if jornada_id:
        qs = qs.filter(journey_id=jornada_id)
    if start and end:
        qs = qs.filter(date__range=(start, end))

    blocks_deleted = qs.count()
    qs.delete()

    return {"blocks_deleted": blocks_deleted}

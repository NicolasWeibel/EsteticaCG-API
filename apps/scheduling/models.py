import uuid

from django.db import models


class AvailabilityBatch(models.Model):
    class Type(models.TextChoices):
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"
        SINGLE = "SINGLE", "Single"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=Type.choices)
    date_start = models.DateField()
    date_end = models.DateField()
    rule = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "availability_batches"


class AvailabilityDay(models.Model):
    journey = models.ForeignKey(
        "catalog.Journey",
        on_delete=models.CASCADE,
        related_name="availability_days",
    )
    date = models.DateField()
    batch_id = models.UUIDField(db_index=True)

    class Meta:
        db_table = "availability_days"
        indexes = [
            models.Index(fields=["journey", "date"]),
            models.Index(fields=["date"]),
        ]


class AvailabilitySlot(models.Model):
    availability_day = models.ForeignKey(
        AvailabilityDay,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        db_table = "availability_slots"
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F("end_time")),
                name="ck_availability_slot_start_lt_end",
            ),
        ]
        indexes = [
            models.Index(fields=["availability_day"]),
        ]


class ScheduleBlock(models.Model):
    journey = models.ForeignKey(
        "catalog.Journey",
        on_delete=models.CASCADE,
        related_name="schedule_blocks",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "schedule_blocks"
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F("end_time")),
                name="ck_schedule_block_start_lt_end",
            ),
        ]
        indexes = [
            models.Index(fields=["journey", "date"]),
            models.Index(fields=["date"]),
        ]

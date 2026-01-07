from django.contrib import admin

from apps.scheduling.models import (
    AvailabilityBatch,
    AvailabilityDay,
    AvailabilitySlot,
    ScheduleBlock,
)


@admin.register(AvailabilityDay)
class AvailabilityDayAdmin(admin.ModelAdmin):
    list_display = ("id", "journey", "date", "batch_id")
    list_filter = ("date", "journey")
    search_fields = ("batch_id", "journey__title", "journey__slug")
    date_hierarchy = "date"


@admin.register(AvailabilityBatch)
class AvailabilityBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "date_start", "date_end", "created_at")
    list_filter = ("type",)
    search_fields = ("id",)


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ("id", "availability_day", "start_time", "end_time")
    list_filter = ("availability_day__date",)
    search_fields = ("availability_day__journey__title", "availability_day__journey__slug")


@admin.register(ScheduleBlock)
class ScheduleBlockAdmin(admin.ModelAdmin):
    list_display = ("id", "journey", "date", "start_time", "end_time", "reason")
    list_filter = ("date", "journey")
    search_fields = ("journey__title", "journey__slug", "reason")
    date_hierarchy = "date"

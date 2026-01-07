from django.urls import path

from apps.scheduling.api.v1.views import (
    AvailabilityBatchDetailView,
    AvailabilityView,
    ScheduleBlockView,
)

app_name = "scheduling"

urlpatterns = [
    path("availability/", AvailabilityView.as_view(), name="availability"),
    path(
        "availability/batches/<uuid:batch_id>/",
        AvailabilityBatchDetailView.as_view(),
        name="availability-batch-detail",
    ),
    path("blocks/", ScheduleBlockView.as_view(), name="blocks"),
]

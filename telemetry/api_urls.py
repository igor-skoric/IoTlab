from django.urls import path

from telemetry.views import DeviceLatestView, TelemetryBatchIngestView, TelemetryIngestView

urlpatterns = [
    path("telemetry/", TelemetryIngestView.as_view(), name="telemetry-ingest"),
    path("telemetry", TelemetryIngestView.as_view()),
    path("telemetry/batch/", TelemetryBatchIngestView.as_view(), name="telemetry-batch"),
    path("telemetry/batch", TelemetryBatchIngestView.as_view()),
    path(
        "devices/<str:device_uid>/latest/",
        DeviceLatestView.as_view(),
        name="device-latest",
    ),
]

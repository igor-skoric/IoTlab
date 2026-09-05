from django.contrib import admin

from telemetry.models import TelemetryReading


@admin.register(TelemetryReading)
class TelemetryReadingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "device",
        "sensor",
        "reading_uid",
        "sensor_uid",
        "reading_type",
        "numeric_value",
        "unit",
        "measured_at",
        "received_at",
    )
    list_filter = ("reading_type", "unit", "device", "measured_at")
    search_fields = (
        "reading_uid",
        "sensor_uid",
        "reading_type",
        "text_value",
        "device__name",
        "device__device_uid",
        "sensor__name",
    )
    date_hierarchy = "measured_at"
    readonly_fields = ("received_at",)
    autocomplete_fields = ("device", "sensor")
    list_select_related = ("device", "sensor")
    list_per_page = 50
    ordering = ("-measured_at", "-id")

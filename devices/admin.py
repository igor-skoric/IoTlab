from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from devices.models import Device, Sensor
from telemetry.models import TelemetryReading


def _mask_api_key(api_key: str) -> str:
    if not api_key or len(api_key) < 12:
        return "••••"
    return f"{api_key[:8]}…{api_key[-4:]}"


class SensorInline(admin.TabularInline):
    model = Sensor
    extra = 0
    fields = ("sensor_uid", "name", "sensor_type", "unit", "is_active")
    readonly_fields = ()


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "device_uid",
        "device_type",
        "is_active",
        "last_seen_at",
        "created_at",
        "masked_api_key",
    )
    list_filter = ("device_type", "is_active")
    search_fields = ("name", "device_uid")
    readonly_fields = ("api_key_copy", "masked_api_key", "created_at", "updated_at", "last_seen_at")
    inlines = [SensorInline]
    actions = ("show_api_keys",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "device_uid",
                    "device_type",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            "Authentication",
            {
                "fields": ("api_key_copy", "masked_api_key"),
                "description": "Click the API key field to select it, then copy. It is also shown in a success message when the device is first created.",
            },
        ),
        (
            "Activity",
            {"fields": ("last_seen_at", "created_at", "updated_at")},
        ),
    )

    @admin.display(description="API key")
    def masked_api_key(self, obj):
        if not obj.pk:
            return "Generated on save"
        return _mask_api_key(obj.api_key)

    @admin.display(description="API key (copy)")
    def api_key_copy(self, obj):
        if not obj.pk:
            return "Generated on save"
        return format_html(
            '<input type="text" value="{}" readonly onclick="this.select();" '
            'style="width:min(40rem,100%);font-family:ui-monospace,monospace;">',
            obj.api_key,
        )

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        if is_new:
            messages.success(
                request,
                f"API key for {obj.device_uid} (copy now): {obj.api_key}",
            )

    @admin.action(description="Show full API keys")
    def show_api_keys(self, request, queryset):
        for device in queryset:
            messages.success(request, f"{device.device_uid}: {device.api_key}")


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "device",
        "sensor_uid",
        "sensor_type",
        "unit",
        "is_active",
        "latest_info",
    )
    list_display_links = ("sensor_uid",)
    list_editable = ("name",)
    list_filter = ("sensor_type", "is_active", "device")
    search_fields = ("name", "sensor_uid", "device__name", "device__device_uid")
    autocomplete_fields = ("device",)
    readonly_fields = ("latest_info", "created_at")
    fieldsets = (
        (
            None,
            {
                "fields": ("device", "sensor_uid", "name", "sensor_type", "unit", "is_active"),
                "description": 'Keep sensor_uid as the device component (e.g. temperature:100). Rename Name to a human label such as "Fridge 1".',
            },
        ),
        ("Latest", {"fields": ("latest_info", "created_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:
            readonly.append("sensor_uid")
            readonly.append("device")
        return readonly

    @admin.display(description="Latest reading")
    def latest_info(self, obj):
        if not obj.pk:
            return "—"
        reading = (
            TelemetryReading.objects.filter(sensor=obj)
            .order_by("-measured_at", "-id")
            .first()
        )
        if not reading:
            return "—"
        value = reading.numeric_value if reading.numeric_value is not None else reading.text_value
        unit = reading.unit or ""
        measured = timezone.localtime(reading.measured_at).strftime("%Y-%m-%d %H:%M:%S %Z")
        return format_html("{} {} <span style='opacity:0.7'>@ {}</span>", value, unit, measured)

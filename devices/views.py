from datetime import timedelta

from django.conf import settings
from django.db.models import OuterRef, Prefetch, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import DetailView, TemplateView

from devices.models import Device, Sensor
from telemetry.models import TelemetryReading


def annotate_latest_reading(queryset):
    latest = TelemetryReading.objects.filter(sensor_id=OuterRef("pk")).order_by(
        "-measured_at",
        "-id",
    )
    return queryset.annotate(
        latest_numeric_value=Subquery(latest.values("numeric_value")[:1]),
        latest_text_value=Subquery(latest.values("text_value")[:1]),
        latest_unit=Subquery(latest.values("unit")[:1]),
        latest_measured_at=Subquery(latest.values("measured_at")[:1]),
        latest_received_at=Subquery(latest.values("received_at")[:1]),
        latest_reading_type=Subquery(latest.values("reading_type")[:1]),
    )


def dashboard_context():
    now = timezone.now()
    window = timedelta(seconds=getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 300))

    sensors = annotate_latest_reading(Sensor.objects.all())
    devices = Device.objects.prefetch_related(
        Prefetch("sensors", queryset=sensors)
    )

    device_rows = []
    online_count = 0
    for device in devices:
        if device.is_online(now=now):
            status = "online"
            online_count += 1
        elif device.last_seen_at:
            status = "stale"
        else:
            status = "offline"
        device_rows.append({"device": device, "status": status})

    return {
        "device_count": Device.objects.count(),
        "online_count": online_count,
        "device_rows": device_rows,
        "online_window_seconds": int(window.total_seconds()),
    }


class DashboardView(TemplateView):
    template_name = "devices/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(dashboard_context())
        return context


class DashboardLiveView(TemplateView):
    template_name = "devices/_dashboard_live.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(dashboard_context())
        return context

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class DeviceDetailView(DetailView):
    template_name = "devices/device_detail.html"
    model = Device
    slug_field = "device_uid"
    slug_url_kwarg = "device_uid"
    context_object_name = "device"

    def get_object(self, queryset=None):
        return get_object_or_404(
            Device.objects.prefetch_related(
                Prefetch("sensors", queryset=annotate_latest_reading(Sensor.objects.all()))
            ),
            device_uid=self.kwargs["device_uid"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        device = self.object
        if device.is_online():
            status = "online"
        elif device.last_seen_at:
            status = "stale"
        else:
            status = "offline"

        context.update(
            {
                "status": status,
                "readings": device.readings.select_related("sensor").order_by(
                    "-measured_at",
                    "-id",
                )[:100],
            }
        )
        return context

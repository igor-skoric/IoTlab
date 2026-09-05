from django.db import models
from django.utils import timezone

from devices.models import Device, Sensor


class TelemetryReading(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="readings")
    sensor = models.ForeignKey(
        Sensor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="readings",
    )
    reading_uid = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Device-generated id used for idempotent retries after offline flush.",
    )
    sensor_uid = models.CharField(max_length=128)
    reading_type = models.CharField(max_length=64)
    numeric_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    text_value = models.CharField(max_length=255, blank=True, null=True)
    unit = models.CharField(max_length=32, blank=True, null=True)
    measured_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    raw_payload = models.JSONField(default=dict)

    class Meta:
        ordering = ["-measured_at", "-id"]
        indexes = [
            models.Index(fields=["device", "measured_at"], name="tel_device_measured_idx"),
            models.Index(fields=["sensor", "measured_at"], name="tel_sensor_measured_idx"),
            models.Index(fields=["received_at"], name="tel_received_at_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "reading_uid"],
                condition=models.Q(reading_uid__isnull=False),
                name="uniq_device_reading_uid",
            )
        ]

    def __str__(self) -> str:
        return f"{self.device_id}:{self.sensor_uid} @ {self.measured_at}"

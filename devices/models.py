import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_api_key() -> str:
    """URL-safe secret suitable for device authentication headers."""
    return secrets.token_urlsafe(40)


class Device(models.Model):
    class DeviceType(models.TextChoices):
        SHELLY = "SHELLY", "Shelly"
        ESP32 = "ESP32", "ESP32"
        LILYGO = "LILYGO", "LILYGO"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=128)
    device_uid = models.CharField(max_length=128, unique=True)
    device_type = models.CharField(
        max_length=16,
        choices=DeviceType.choices,
        default=DeviceType.OTHER,
    )
    description = models.TextField(blank=True)
    api_key = models.CharField(max_length=128, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.device_uid})"

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = generate_api_key()
        super().save(*args, **kwargs)

    def is_online(self, now=None, window_seconds=None) -> bool:
        if not self.last_seen_at:
            return False
        now = now or timezone.now()
        window = window_seconds
        if window is None:
            window = getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 300)
        return self.last_seen_at >= now - timedelta(seconds=window)


class Sensor(models.Model):
    class SensorType(models.TextChoices):
        TEMPERATURE = "TEMPERATURE", "Temperature"
        HUMIDITY = "HUMIDITY", "Humidity"
        DOOR = "DOOR", "Door"
        LEAK = "LEAK", "Leak"
        OTHER = "OTHER", "Other"

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="sensors")
    sensor_uid = models.CharField(max_length=128)
    name = models.CharField(max_length=128)
    sensor_type = models.CharField(
        max_length=16,
        choices=SensorType.choices,
        default=SensorType.OTHER,
    )
    unit = models.CharField(max_length=32, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "sensor_uid"],
                name="uniq_device_sensor_uid",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sensor_uid})"

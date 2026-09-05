from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from devices.models import Device, Sensor
from telemetry.models import TelemetryReading


class WebUITests(TestCase):
    def setUp(self):
        self.device = Device.objects.create(
            name="Fridge monitor",
            device_uid="shelly-plus-uni-01",
            device_type=Device.DeviceType.SHELLY,
        )
        self.sensor = Sensor.objects.create(
            device=self.device,
            sensor_uid="temperature:100",
            name="Fridge 1",
            sensor_type=Sensor.SensorType.TEMPERATURE,
            unit="C",
        )
        TelemetryReading.objects.create(
            device=self.device,
            sensor=self.sensor,
            sensor_uid="temperature:100",
            reading_type="temperature",
            numeric_value="27.3",
            unit="C",
            measured_at=timezone.now(),
            raw_payload={"sensor_uid": "temperature:100"},
        )

    def test_health(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_dashboard(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fridge monitor")
        self.assertContains(response, "27.3")
        self.assertContains(response, "Measured at")
        self.assertContains(response, "Received at")
        self.assertContains(response, "hx-get")
        self.assertContains(response, reverse("dashboard-live"))
        self.assertContains(response, "every 5s")

    def test_dashboard_live_partial(self):
        response = self.client.get(reverse("dashboard-live"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertContains(response, "Fridge monitor")
        self.assertContains(response, "27.3")
        self.assertContains(response, "status-offline")
        self.assertNotContains(response, "<html")
        self.assertNotContains(response, "Device telemetry")

    def test_device_detail(self):
        response = self.client.get(reverse("device-detail", kwargs={"device_uid": "shelly-plus-uni-01"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fridge 1")
        self.assertContains(response, "temperature:100")
        self.assertContains(response, "Measured at")
        self.assertContains(response, "Received at")
        self.assertContains(response, "Reading uid")

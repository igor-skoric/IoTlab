from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from devices.models import Device, Sensor
from telemetry.models import TelemetryReading


class TelemetryAPITests(APITestCase):
    def setUp(self):
        self.device = Device.objects.create(
            name="Fridge monitor",
            device_uid="shelly-plus-uni-01",
            device_type=Device.DeviceType.SHELLY,
        )
        self.ingest_url = reverse("telemetry-ingest")
        self.latest_url = reverse("device-latest", kwargs={"device_uid": self.device.device_uid})
        self.payload = {
            "sensor_uid": "temperature:100",
            "type": "temperature",
            "value": 27.3,
            "unit": "C",
        }

    def _post(self, payload=None, api_key=None):
        headers = {}
        key = self.device.api_key if api_key is None else api_key
        if key:
            headers["HTTP_X_API_KEY"] = key
        return self.client.post(
            self.ingest_url,
            payload or self.payload,
            format="json",
            **headers,
        )

    def test_valid_telemetry_post(self):
        response = self._post()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["device"], "shelly-plus-uni-01")
        self.assertIsNotNone(response.data["reading_id"])
        reading = TelemetryReading.objects.get(pk=response.data["reading_id"])
        self.assertEqual(reading.sensor_uid, "temperature:100")
        self.assertEqual(reading.numeric_value, Decimal("27.3"))
        self.assertEqual(reading.unit, "C")
        self.assertIsNotNone(reading.measured_at)
        self.assertEqual(reading.raw_payload["sensor_uid"], "temperature:100")

    def test_shelly_plus_uni_payload(self):
        payload = {
            "reading_uid": "unique-id",
            "sensor_uid": "temperature:100",
            "type": "temperature",
            "value": 27.3,
            "unit": "C",
            "measured_at": "2026-09-05T18:10:00+02:00",
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["reading_uid"], "unique-id")
        reading = TelemetryReading.objects.get(pk=response.data["reading_id"])
        self.assertEqual(reading.reading_uid, "unique-id")
        self.assertEqual(reading.sensor_uid, "temperature:100")
        self.assertEqual(reading.numeric_value, Decimal("27.3"))
        self.assertEqual(reading.unit, "C")
        self.assertEqual(reading.measured_at, parse_datetime("2026-09-05T18:10:00+02:00"))
        self.assertIsNotNone(reading.received_at)
        self.assertNotEqual(reading.measured_at, reading.received_at)

    def test_invalid_api_key(self):
        response = self._post(api_key="not-a-real-key")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(TelemetryReading.objects.count(), 0)

    def test_missing_api_key(self):
        response = self._post(api_key="")
        self.assertEqual(response.status_code, 401)

    def test_inactive_device(self):
        self.device.is_active = False
        self.device.save(update_fields=["is_active", "updated_at"])
        response = self._post()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(TelemetryReading.objects.count(), 0)

    def test_auto_created_sensor(self):
        self.assertEqual(Sensor.objects.count(), 0)
        response = self._post()
        self.assertEqual(response.status_code, 201)
        sensor = Sensor.objects.get(device=self.device, sensor_uid="temperature:100")
        self.assertEqual(sensor.sensor_type, Sensor.SensorType.TEMPERATURE)
        self.assertEqual(sensor.unit, "C")
        reading = TelemetryReading.objects.get(pk=response.data["reading_id"])
        self.assertEqual(reading.sensor_id, sensor.id)

    def test_last_seen_at_updated(self):
        self.assertIsNone(self.device.last_seen_at)
        before = timezone.now()
        response = self._post()
        self.assertEqual(response.status_code, 201)
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)
        self.assertGreaterEqual(self.device.last_seen_at, before)

    def test_latest_readings_endpoint(self):
        first = self._post(
            {
                "sensor_uid": "temperature:100",
                "type": "temperature",
                "value": 21.0,
                "unit": "C",
            }
        )
        self.assertEqual(first.status_code, 201)
        second = self._post(
            {
                "sensor_uid": "temperature:100",
                "type": "temperature",
                "value": 27.3,
                "unit": "C",
            }
        )
        self.assertEqual(second.status_code, 201)
        self._post(
            {
                "sensor_uid": "humidity:1",
                "type": "humidity",
                "value": 48.1,
                "unit": "%",
            }
        )

        response = self.client.get(self.latest_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["device_uid"], "shelly-plus-uni-01")
        self.assertIsNotNone(response.data["last_seen_at"])
        sensors = {item["sensor_uid"]: item for item in response.data["sensors"]}
        self.assertEqual(sensors["temperature:100"]["value"], 27.3)
        self.assertEqual(sensors["temperature:100"]["unit"], "C")
        self.assertEqual(sensors["humidity:1"]["value"], 48.1)
        self.assertEqual(sensors["temperature:100"]["name"], "temperature:100")

    def test_latest_unknown_device(self):
        response = self.client.get("/api/v1/devices/does-not-exist/latest/")
        self.assertEqual(response.status_code, 404)

    def test_validation_requires_value(self):
        response = self._post({"sensor_uid": "temperature:100", "type": "temperature"})
        self.assertEqual(response.status_code, 400)

    def test_measured_at_uses_payload_or_server_time(self):
        response = self._post(
            {
                "sensor_uid": "temperature:100",
                "type": "temperature",
                "value": 18.5,
                "unit": "C",
                "measured_at": "2026-09-05T17:30:00+02:00",
            }
        )
        self.assertEqual(response.status_code, 201)
        reading = TelemetryReading.objects.get(pk=response.data["reading_id"])
        self.assertEqual(reading.measured_at, parse_datetime("2026-09-05T17:30:00+02:00"))


class TelemetryBatchAPITests(APITestCase):
    def setUp(self):
        self.device = Device.objects.create(
            name="Fridge monitor",
            device_uid="shelly-plus-uni-01",
            device_type=Device.DeviceType.SHELLY,
        )
        self.batch_url = reverse("telemetry-batch")
        self.ingest_url = reverse("telemetry-ingest")

    def _headers(self):
        return {"HTTP_X_API_KEY": self.device.api_key}

    def _reading(self, uid, value, measured_at, reading_uid=None):
        payload = {
            "sensor_uid": uid,
            "type": "temperature",
            "value": value,
            "unit": "C",
            "measured_at": measured_at,
        }
        if reading_uid:
            payload["reading_uid"] = reading_uid
        return payload

    def test_batch_telemetry_upload(self):
        payload = {
            "readings": [
                self._reading(
                    "temperature:100",
                    4.2,
                    "2026-09-05T12:00:00+02:00",
                    "550e8400-e29b-41d4-a716-446655440000",
                ),
                self._reading(
                    "temperature:100",
                    4.3,
                    "2026-09-05T12:02:00+02:00",
                    "550e8400-e29b-41d4-a716-446655440001",
                ),
            ]
        }
        response = self.client.post(self.batch_url, payload, format="json", **self._headers())
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["accepted"], 2)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["rejected"], 0)
        self.assertEqual(TelemetryReading.objects.count(), 2)
        self.assertEqual(response.data["results"][0]["status"], "created")
        self.assertEqual(
            response.data["results"][0]["reading_uid"],
            "550e8400-e29b-41d4-a716-446655440000",
        )

    def test_batch_preserves_original_measured_at(self):
        payload = {
            "readings": [
                self._reading(
                    "temperature:100",
                    4.2,
                    "2026-09-05T12:00:00+02:00",
                    "uid-a",
                ),
                self._reading(
                    "temperature:100",
                    4.3,
                    "2026-09-05T12:02:00+02:00",
                    "uid-b",
                ),
            ]
        }
        before = timezone.now()
        response = self.client.post(self.batch_url, payload, format="json", **self._headers())
        self.assertEqual(response.status_code, 201)

        first = TelemetryReading.objects.get(reading_uid="uid-a")
        second = TelemetryReading.objects.get(reading_uid="uid-b")
        self.assertEqual(first.measured_at, parse_datetime("2026-09-05T12:00:00+02:00"))
        self.assertEqual(second.measured_at, parse_datetime("2026-09-05T12:02:00+02:00"))
        self.assertGreaterEqual(first.received_at, before)
        self.assertGreaterEqual(second.received_at, before)
        self.assertNotEqual(first.measured_at, first.received_at)
        self.assertNotEqual(second.measured_at, second.received_at)
        self.assertEqual(first.received_at, second.received_at)

    def test_received_at_is_server_generated(self):
        measured = "2026-01-01T00:00:00+00:00"
        before = timezone.now()
        response = self.client.post(
            self.ingest_url,
            self._reading("temperature:100", 1.5, measured, "uid-received"),
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, 201)
        reading = TelemetryReading.objects.get(reading_uid="uid-received")
        self.assertEqual(reading.measured_at, parse_datetime(measured))
        self.assertGreaterEqual(reading.received_at, before)
        self.assertNotEqual(reading.measured_at, reading.received_at)

    def test_duplicate_reading_uid_on_single_post(self):
        payload = self._reading(
            "temperature:100",
            4.2,
            "2026-09-05T12:00:00+02:00",
            "same-uid",
        )
        first = self.client.post(self.ingest_url, payload, format="json", **self._headers())
        self.assertEqual(first.status_code, 201)
        payload["value"] = 99.9
        second = self.client.post(self.ingest_url, payload, format="json", **self._headers())
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["status"], "duplicate")
        self.assertEqual(second.data["reading_id"], first.data["reading_id"])
        self.assertEqual(TelemetryReading.objects.count(), 1)
        reading = TelemetryReading.objects.get()
        self.assertEqual(reading.numeric_value, Decimal("4.2"))

    def test_retrying_the_same_batch_does_not_duplicate_rows(self):
        payload = {
            "readings": [
                self._reading(
                    "temperature:100",
                    4.2,
                    "2026-09-05T12:00:00+02:00",
                    "uid-a",
                ),
                self._reading(
                    "temperature:100",
                    4.3,
                    "2026-09-05T12:02:00+02:00",
                    "uid-b",
                ),
            ]
        }
        first = self.client.post(self.batch_url, payload, format="json", **self._headers())
        self.assertEqual(first.status_code, 201)
        second = self.client.post(self.batch_url, payload, format="json", **self._headers())
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["success"])
        self.assertEqual(second.data["created"], 0)
        self.assertEqual(second.data["duplicates"], 2)
        self.assertEqual(TelemetryReading.objects.count(), 2)
        self.assertEqual(
            {item["reading_id"] for item in second.data["results"]},
            {item["reading_id"] for item in first.data["results"]},
        )

    def test_one_invalid_reading_does_not_drop_the_rest(self):
        payload = {
            "readings": [
                self._reading(
                    "temperature:100",
                    4.2,
                    "2026-09-05T12:00:00+02:00",
                    "uid-good",
                ),
                {"sensor_uid": "temperature:100", "type": "temperature"},
                self._reading(
                    "temperature:100",
                    4.4,
                    "2026-09-05T12:04:00+02:00",
                    "uid-good-2",
                ),
            ]
        }
        response = self.client.post(self.batch_url, payload, format="json", **self._headers())
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["rejected"], 1)
        self.assertEqual(TelemetryReading.objects.count(), 2)
        self.assertEqual(response.data["results"][1]["status"], "rejected")
        self.assertIn("errors", response.data["results"][1])

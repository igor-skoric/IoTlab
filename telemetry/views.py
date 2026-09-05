from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.models import Device
from devices.views import annotate_latest_reading
from telemetry.authentication import DeviceAPIKeyAuthentication, IsActiveDevice
from telemetry.serializers import TelemetryBatchSerializer, TelemetryIngestSerializer
from telemetry.services import ingest_reading_batch, ingest_telemetry


def _decimal_or_text(numeric_value, text_value):
    if numeric_value is not None:
        return float(numeric_value)
    return text_value


def _item_payload(item):
    payload = {
        "index": item.index,
        "status": item.status,
        "reading_id": item.reading_id,
        "reading_uid": item.reading_uid,
    }
    if item.errors:
        payload["errors"] = item.errors
    return payload


class TelemetryIngestView(APIView):
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = [IsActiveDevice]

    def post(self, request):
        serializer = TelemetryIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ingest_telemetry(
            device=request.user,
            validated_data=serializer.validated_data,
            raw_payload=dict(request.data),
        )
        http_status = (
            status.HTTP_201_CREATED if result.status == "created" else status.HTTP_200_OK
        )
        return Response(
            {
                "success": True,
                "reading_id": result.reading_id,
                "reading_uid": result.reading_uid,
                "device": request.user.device_uid,
                "status": result.status,
            },
            status=http_status,
        )


class TelemetryBatchIngestView(APIView):
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = [IsActiveDevice]

    def post(self, request):
        serializer = TelemetryBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = ingest_reading_batch(request.user, serializer.validated_data["readings"])

        if outcome.accepted_count == 0:
            http_status = status.HTTP_400_BAD_REQUEST
        elif outcome.created_count:
            http_status = status.HTTP_201_CREATED
        else:
            http_status = status.HTTP_200_OK

        return Response(
            {
                "success": outcome.success,
                "device": request.user.device_uid,
                "accepted": outcome.accepted_count,
                "created": outcome.created_count,
                "duplicates": outcome.duplicate_count,
                "rejected": outcome.rejected_count,
                "results": [_item_payload(item) for item in outcome.results],
            },
            status=http_status,
        )


class DeviceLatestView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, device_uid):
        try:
            device = Device.objects.get(device_uid=device_uid)
        except Device.DoesNotExist:
            return Response({"detail": "Device not found."}, status=status.HTTP_404_NOT_FOUND)

        sensors = annotate_latest_reading(device.sensors.all())
        payload = {
            "device_uid": device.device_uid,
            "last_seen_at": device.last_seen_at,
            "sensors": [
                {
                    "sensor_uid": sensor.sensor_uid,
                    "name": sensor.name,
                    "type": (sensor.latest_reading_type or sensor.sensor_type).lower(),
                    "value": _decimal_or_text(
                        sensor.latest_numeric_value,
                        sensor.latest_text_value,
                    ),
                    "unit": sensor.latest_unit or sensor.unit,
                    "measured_at": sensor.latest_measured_at,
                }
                for sensor in sensors
            ],
        }
        return Response(payload)

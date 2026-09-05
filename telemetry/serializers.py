from decimal import Decimal, InvalidOperation

from django.conf import settings
from rest_framework import serializers


class TelemetryIngestSerializer(serializers.Serializer):
    reading_uid = serializers.CharField(max_length=128, required=False, allow_blank=True, allow_null=True)
    sensor_uid = serializers.CharField(max_length=128)
    type = serializers.CharField(max_length=64)
    value = serializers.JSONField(required=False, allow_null=True)
    text_value = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    unit = serializers.CharField(max_length=32, required=False, allow_blank=True, allow_null=True)
    measured_at = serializers.DateTimeField(required=False)
    payload = serializers.JSONField(required=False)

    def validate(self, attrs):
        value = attrs.get("value", None)
        text_value = attrs.get("text_value")
        if value is None and not text_value:
            raise serializers.ValidationError("Provide a numeric 'value' or 'text_value'.")
        return attrs

    def validate_reading_uid(self, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    def validate_value(self, value):
        if value is None:
            return None
        if isinstance(value, bool):
            raise serializers.ValidationError("Boolean values are not valid sensor readings.")
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return Decimal(stripped)
            except InvalidOperation as exc:
                raise serializers.ValidationError("value must be numeric.") from exc
        raise serializers.ValidationError("value must be numeric.")


class TelemetryBatchSerializer(serializers.Serializer):
    readings = serializers.ListField(allow_empty=False)

    def validate_readings(self, readings):
        max_n = getattr(settings, "TELEMETRY_BATCH_MAX_READINGS", 500)
        if len(readings) > max_n:
            raise serializers.ValidationError(f"A batch may contain at most {max_n} readings.")
        return readings

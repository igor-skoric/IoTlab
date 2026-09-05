from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.utils import timezone

from devices.models import Device, Sensor
from telemetry.models import TelemetryReading
from telemetry.serializers import TelemetryIngestSerializer

SENSOR_TYPE_MAP = {
    "TEMPERATURE": Sensor.SensorType.TEMPERATURE,
    "HUMIDITY": Sensor.SensorType.HUMIDITY,
    "DOOR": Sensor.SensorType.DOOR,
    "LEAK": Sensor.SensorType.LEAK,
}


def map_sensor_type(reading_type: str) -> str:
    key = (reading_type or "").strip().upper()
    return SENSOR_TYPE_MAP.get(key, Sensor.SensorType.OTHER)


def coerce_measured_at(measured_at):
    """Keep the device timestamp when present; otherwise use server time."""
    if measured_at is None:
        return timezone.now()
    if timezone.is_naive(measured_at):
        return timezone.make_aware(measured_at, timezone.get_current_timezone())
    return measured_at


@dataclass
class IngestItemResult:
    index: int
    status: str
    reading_id: int | None = None
    reading_uid: str | None = None
    errors: dict | list | None = None


@dataclass
class BatchIngestResult:
    results: list[IngestItemResult] = field(default_factory=list)
    created_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0

    @property
    def accepted_count(self) -> int:
        return self.created_count + self.duplicate_count

    @property
    def success(self) -> bool:
        return self.rejected_count == 0 and self.accepted_count > 0


def ingest_telemetry(device, validated_data, raw_payload=None) -> IngestItemResult:
    batch = ingest_reading_batch(
        device,
        [raw_payload or validated_data],
        prevalidated=[validated_data],
    )
    return batch.results[0]


def ingest_reading_batch(device: Device, raw_items, prevalidated=None) -> BatchIngestResult:
    """
    Validate each reading independently, insert new rows in bulk, and treat
    existing (device, reading_uid) pairs as successful duplicates.
    """
    received_at = timezone.now()
    outcome = BatchIngestResult()
    pending: list[tuple[int, dict, dict]] = []
    seen_uids: dict[str, int] = {}

    for index, raw in enumerate(raw_items):
        if prevalidated is None and not isinstance(raw, dict):
            outcome.results.append(
                IngestItemResult(
                    index=index,
                    status="rejected",
                    errors={"non_field_errors": ["Each reading must be a JSON object."]},
                )
            )
            continue

        if prevalidated is None:
            serializer = TelemetryIngestSerializer(data=raw)
            if not serializer.is_valid():
                outcome.results.append(
                    IngestItemResult(
                        index=index,
                        status="rejected",
                        reading_uid=_raw_reading_uid(raw),
                        errors=serializer.errors,
                    )
                )
                continue
            validated = serializer.validated_data
            raw_payload = dict(raw)
        else:
            validated = prevalidated[index]
            raw_payload = raw if isinstance(raw, dict) else {}

        reading_uid = validated.get("reading_uid") or None
        if reading_uid and reading_uid in seen_uids:
            outcome.results.append(
                IngestItemResult(
                    index=index,
                    status="duplicate",
                    reading_uid=reading_uid,
                )
            )
            continue

        if reading_uid:
            seen_uids[reading_uid] = index

        outcome.results.append(
            IngestItemResult(index=index, status="pending", reading_uid=reading_uid)
        )
        pending.append((index, validated, raw_payload))

    if pending:
        try:
            with transaction.atomic():
                _persist_pending(device, pending, outcome, received_at)
        except IntegrityError:
            with transaction.atomic():
                _persist_pending(device, pending, outcome, received_at)
        device.last_seen_at = received_at
        device.save(update_fields=["last_seen_at", "updated_at"])

    _fill_duplicate_ids(outcome)
    outcome.created_count = sum(1 for item in outcome.results if item.status == "created")
    outcome.duplicate_count = sum(1 for item in outcome.results if item.status == "duplicate")
    outcome.rejected_count = sum(1 for item in outcome.results if item.status == "rejected")
    return outcome


def _raw_reading_uid(raw) -> str | None:
    value = raw.get("reading_uid") if isinstance(raw, dict) else None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _persist_pending(device, pending, outcome: BatchIngestResult, received_at) -> None:
    uids = [validated.get("reading_uid") for _, validated, _ in pending if validated.get("reading_uid")]
    existing = {}
    if uids:
        existing = {
            row.reading_uid: row
            for row in TelemetryReading.objects.filter(device=device, reading_uid__in=uids)
        }

    sensors = _ensure_sensors(
        device,
        [
            (
                validated["sensor_uid"].strip(),
                validated["type"].strip(),
                validated.get("unit") or None,
            )
            for _, validated, _ in pending
            if (validated.get("reading_uid") or None) not in existing
        ],
    )

    to_create: list[TelemetryReading] = []
    create_indexes: list[int] = []

    for index, validated, raw_payload in pending:
        reading_uid = validated.get("reading_uid") or None
        if reading_uid and reading_uid in existing:
            _mark_result(outcome, index, "duplicate", existing[reading_uid])
            continue

        sensor_uid = validated["sensor_uid"].strip()
        to_create.append(
            TelemetryReading(
                device=device,
                sensor=sensors[sensor_uid],
                reading_uid=reading_uid,
                sensor_uid=sensor_uid,
                reading_type=validated["type"].strip(),
                numeric_value=validated.get("value"),
                text_value=validated.get("text_value") or None,
                unit=validated.get("unit") or None,
                measured_at=coerce_measured_at(validated.get("measured_at")),
                received_at=received_at,
                raw_payload=raw_payload,
            )
        )
        create_indexes.append(index)

    if not to_create:
        return

    created_rows = list(TelemetryReading.objects.bulk_create(to_create))
    if created_rows and created_rows[0].pk is None:
        created_rows = _reload_created(device, to_create)

    for index, row in zip(create_indexes, created_rows):
        if row.reading_uid:
            existing[row.reading_uid] = row
        _mark_result(outcome, index, "created", row)


def _reload_created(device, rows: list[TelemetryReading]) -> list[TelemetryReading]:
    uids = [row.reading_uid for row in rows if row.reading_uid]
    fetched = {
        row.reading_uid: row
        for row in TelemetryReading.objects.filter(device=device, reading_uid__in=uids)
    }
    return [fetched.get(row.reading_uid, row) for row in rows]


def _fill_duplicate_ids(outcome: BatchIngestResult) -> None:
    by_uid = {
        item.reading_uid: item.reading_id
        for item in outcome.results
        if item.reading_uid and item.reading_id
    }
    for item in outcome.results:
        if item.status == "duplicate" and item.reading_id is None and item.reading_uid:
            item.reading_id = by_uid.get(item.reading_uid)


def _mark_result(outcome: BatchIngestResult, index: int, status: str, row: TelemetryReading) -> None:
    for item in outcome.results:
        if item.index == index:
            item.status = status
            item.reading_id = row.id
            item.reading_uid = row.reading_uid
            return


def _ensure_sensors(device: Device, specs: list[tuple[str, str, str | None]]) -> dict[str, Sensor]:
    uids = list(dict.fromkeys(sensor_uid for sensor_uid, _type, _unit in specs))
    if not uids:
        return {}

    found = {
        sensor.sensor_uid: sensor
        for sensor in Sensor.objects.filter(device=device, sensor_uid__in=uids)
    }
    to_create = []
    queued = set()
    for sensor_uid, reading_type, unit in specs:
        if sensor_uid in found or sensor_uid in queued:
            continue
        to_create.append(
            Sensor(
                device=device,
                sensor_uid=sensor_uid,
                name=sensor_uid,
                sensor_type=map_sensor_type(reading_type),
                unit=unit,
            )
        )
        queued.add(sensor_uid)

    if to_create:
        try:
            Sensor.objects.bulk_create(to_create)
        except IntegrityError:
            pass
        found = {
            sensor.sensor_uid: sensor
            for sensor in Sensor.objects.filter(device=device, sensor_uid__in=uids)
        }
    return found

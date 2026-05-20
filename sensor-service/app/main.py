from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.parkease_common import (
    ParkingSpot,
    ParkingType,
    Role,
    SensorBatch,
    SensorEvent,
    SensorEventType,
    Settings,
    SpotStatus,
    build_audit_event,
    detect_sensor_anomalies,
    has_permission,
)

settings = Settings(service_name="sensor-service", service_port=8403)
app = FastAPI(title="ParkEase Sensor Service", version="1.0.0")

spots: dict[str, ParkingSpot] = {
    "SPOT-C1-001": ParkingSpot(spot_id="SPOT-C1-001", parking_id="PARK-CENTER-01", parking_type=ParkingType.MULTILEVEL),
    "SPOT-C1-002": ParkingSpot(
        spot_id="SPOT-C1-002",
        parking_id="PARK-CENTER-01",
        parking_type=ParkingType.MULTILEVEL,
        status=SpotStatus.OCCUPIED,
        plate_number="E777AA77",
    ),
    "SPOT-A7-014": ParkingSpot(spot_id="SPOT-A7-014", parking_id="PARK-STREET-07", parking_type=ParkingType.STREET),
    "SPOT-P11-006": ParkingSpot(
        spot_id="SPOT-P11-006",
        parking_id="PARK-PRIVATE-11",
        parking_type=ParkingType.PRIVATE,
        status=SpotStatus.RESERVED,
    ),
}

reserved_by_booking: dict[str, str] = {"BOOK-DEMO": "SPOT-C1-001"}
plate_to_booking: dict[str, str] = {"A123BC77": "BOOK-DEMO"}
sensor_events: list[SensorEvent] = []
audit_log: list[dict[str, Any]] = []
stream_rate_samples: list[int] = [36, 41, 33, 52, 40]


class ReserveSpotRequest(BaseModel):
    booking_id: str
    plate_number: str
    actor_id: str
    actor_role: Role


class ReleaseSpotRequest(BaseModel):
    actor_id: str
    actor_role: Role


class PlateRecognitionRequest(BaseModel):
    plate_number: str
    parking_id: str
    confidence: float = Field(default=0.95, ge=0, le=1)


class SpotStatusRequest(BaseModel):
    status: SpotStatus
    actor_id: str
    actor_role: Role


ReserveSpotRequest.model_rebuild()
ReleaseSpotRequest.model_rebuild()
PlateRecognitionRequest.model_rebuild()
SpotStatusRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="sensor",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _spot_or_404(spot_id: str) -> ParkingSpot:
    spot = spots.get(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    return spot


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/spots")
async def list_spots(parking_id: str | None = None, status: SpotStatus | None = None) -> dict[str, Any]:
    items = []
    for spot in spots.values():
        if parking_id and spot.parking_id != parking_id:
            continue
        if status and spot.status != status:
            continue
        items.append(spot.model_dump(mode="json"))
    return {"items": items, "count": len(items)}


@app.post("/spots/{spot_id}/reserve")
async def reserve_spot(spot_id: str, request: ReserveSpotRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "sensor:reserve")
    spot = _spot_or_404(spot_id)
    if spot.status != SpotStatus.FREE:
        raise HTTPException(status_code=409, detail="Spot is not free")
    spot.status = SpotStatus.RESERVED
    spot.plate_number = request.plate_number
    spot.updated_at = datetime.now(UTC)
    reserved_by_booking[request.booking_id] = spot_id
    plate_to_booking[request.plate_number.upper()] = request.booking_id
    _audit(request.actor_id, request.actor_role, "sensor.reserve", spot_id, {"booking_id": request.booking_id})
    return spot.model_dump(mode="json")


@app.post("/spots/{spot_id}/release")
async def release_spot(spot_id: str, request: ReleaseSpotRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "sensor:reserve")
    spot = _spot_or_404(spot_id)
    spot.status = SpotStatus.FREE
    spot.plate_number = None
    spot.updated_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "sensor.release", spot_id)
    return spot.model_dump(mode="json")


@app.post("/spots/{spot_id}/status")
async def set_status(spot_id: str, request: SpotStatusRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "sensor:write")
    spot = _spot_or_404(spot_id)
    spot.status = request.status
    spot.updated_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "sensor.status", spot_id, {"status": request.status.value})
    return spot.model_dump(mode="json")


@app.post("/sensors/ingest")
async def ingest_sensor_events(batch: SensorBatch) -> dict[str, Any]:
    _assert_permission(batch.actor_role, "sensor:write")
    accepted = 0
    for event in batch.events:
        spot = spots.get(event.spot_id)
        if spot:
            if event.event_type == SensorEventType.OCCUPANCY and event.occupied is not None:
                spot.status = SpotStatus.OCCUPIED if event.occupied else SpotStatus.FREE
            if event.plate_number:
                spot.plate_number = event.plate_number
            spot.updated_at = event.event_time
        sensor_events.append(event)
        accepted += 1
    stream_rate_samples.append(accepted)
    stream_rate_samples[:] = stream_rate_samples[-120:]
    return {"accepted": accepted, "queue": "mqtt:parking/occupancy"}


@app.post("/plates/recognize")
async def recognize_plate(request: PlateRecognitionRequest) -> dict[str, Any]:
    booking_id = plate_to_booking.get(request.plate_number.upper())
    gate_action = "open" if booking_id and request.confidence >= 0.8 else "manual_check"
    event = SensorEvent(
        event_id=str(uuid4()),
        spot_id=reserved_by_booking.get(booking_id, "UNKNOWN") if booking_id else "UNKNOWN",
        parking_id=request.parking_id,
        event_type=SensorEventType.PLATE_DETECTED,
        plate_number=request.plate_number,
        confidence=request.confidence,
        source="camera",
    )
    sensor_events.append(event)
    return {
        "recognized": booking_id is not None,
        "booking_id": booking_id,
        "gate_action": gate_action,
        "event": event.model_dump(mode="json"),
    }


@app.get("/reservations/{booking_id}")
async def get_reservation(booking_id: str) -> dict[str, Any]:
    spot_id = reserved_by_booking.get(booking_id)
    if spot_id is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return {"booking_id": booking_id, "spot_id": spot_id}


@app.get("/stream/health")
async def stream_health() -> dict[str, Any]:
    anomalies = detect_sensor_anomalies(stream_rate_samples[-20:])
    return {
        "events_buffered": len(sensor_events),
        "recent_rate": stream_rate_samples[-1] if stream_rate_samples else 0,
        "anomalies": anomalies,
    }


@app.get("/processing/plan")
async def processing_plan(track_count: int = 10000, districts: int = 12) -> dict[str, Any]:
    workers = min(64, max(2, districts * 2, track_count // 250))
    batch_size = max(100, track_count // workers)
    return {
        "workers": workers,
        "batch_size": batch_size,
        "transport": "mqtt+rabbitmq",
        "mode": "streaming",
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

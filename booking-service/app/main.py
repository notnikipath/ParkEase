from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.parkease_common import (
    BookingCreateRequest,
    BookingExtendRequest,
    BookingRecord,
    BookingStatus,
    Role,
    Settings,
    build_audit_event,
    calculate_dynamic_price,
    has_permission,
)

settings = Settings(service_name="booking-service", service_port=8401)
app = FastAPI(title="ParkEase Booking Service", version="1.0.0")

parking_base_prices: dict[str, float] = {
    "PARK-CENTER-01": 190,
    "PARK-STREET-07": 120,
    "PARK-PRIVATE-11": 240,
}

spot_to_booking: dict[str, str] = {}
bookings: dict[str, BookingRecord] = {}
audit_log: list[dict[str, Any]] = []


def _seed_demo() -> None:
    start = datetime.now(UTC)
    duration = 90
    rate = calculate_dynamic_price(parking_base_prices["PARK-CENTER-01"], occupancy_ratio=0.62, peak_multiplier=1.05)
    booking = BookingRecord(
        booking_id="BOOK-DEMO",
        user_id="USER-001",
        parking_id="PARK-CENTER-01",
        spot_id="SPOT-DEMO-001",
        plate_number="A123BC77",
        start_at=start,
        end_at=start + timedelta(minutes=duration),
        reserved_until=start + timedelta(minutes=15),
        rate_per_hour=rate,
        total_price=round(rate * duration / 60, 2),
        status=BookingStatus.CONFIRMED,
    )
    bookings[booking.booking_id] = booking
    spot_to_booking[booking.spot_id] = booking.booking_id


_seed_demo()


class StatusUpdateRequest(BaseModel):
    status: BookingStatus
    actor_id: str
    actor_role: Role


class CancelRequest(BaseModel):
    actor_id: str
    actor_role: Role


StatusUpdateRequest.model_rebuild()
CancelRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="booking",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _is_spot_busy(spot_id: str) -> bool:
    booking_id = spot_to_booking.get(spot_id)
    if not booking_id:
        return False
    booking = bookings.get(booking_id)
    if booking is None:
        return False
    return booking.status in {BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.ACTIVE}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/bookings")
async def list_bookings(user_id: str | None = None, status: BookingStatus | None = None) -> dict[str, Any]:
    items = []
    for booking in bookings.values():
        if user_id and booking.user_id != user_id:
            continue
        if status and booking.status != status:
            continue
        items.append(booking.model_dump(mode="json"))
    return {"items": items, "count": len(items)}


@app.get("/bookings/{booking_id}")
async def get_booking(booking_id: str) -> dict[str, Any]:
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking.model_dump(mode="json")


@app.post("/bookings")
async def create_booking(request: BookingCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:create")
    if _is_spot_busy(request.spot_id):
        raise HTTPException(status_code=409, detail="Spot already booked")

    base_price = parking_base_prices.get(request.parking_id, 150)
    occupancy_ratio = 0.6 if request.parking_id == "PARK-CENTER-01" else 0.45
    rate = calculate_dynamic_price(base_price, occupancy_ratio=occupancy_ratio, peak_multiplier=1.08)

    now = datetime.now(UTC)
    booking = BookingRecord(
        booking_id=str(uuid4()),
        user_id=request.user_id,
        parking_id=request.parking_id,
        spot_id=request.spot_id,
        plate_number=request.plate_number,
        start_at=now,
        end_at=now + timedelta(minutes=request.duration_minutes),
        reserved_until=now + timedelta(minutes=15),
        rate_per_hour=rate,
        total_price=round(rate * request.duration_minutes / 60, 2),
        status=BookingStatus.PENDING,
    )
    bookings[booking.booking_id] = booking
    spot_to_booking[request.spot_id] = booking.booking_id
    _audit(request.user_id, request.actor_role, "booking.create", booking.booking_id, {"spot_id": request.spot_id})
    return booking.model_dump(mode="json")


@app.post("/bookings/{booking_id}/extend")
async def extend_booking(booking_id: str, request: BookingExtendRequest) -> dict[str, Any]:
    action = "booking:extend" if request.actor_role in {Role.ADMIN, Role.OPERATOR} else "booking:extend:own"
    _assert_permission(request.actor_role, action)

    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status not in {BookingStatus.CONFIRMED, BookingStatus.ACTIVE, BookingStatus.PENDING}:
        raise HTTPException(status_code=409, detail="Booking cannot be extended in current status")

    booking.end_at += timedelta(minutes=request.extra_minutes)
    booking.total_price = round(booking.total_price + booking.rate_per_hour * request.extra_minutes / 60, 2)
    return booking.model_dump(mode="json")


@app.post("/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, request: StatusUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "booking:update")
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = request.status
    _audit(request.actor_id, request.actor_role, "booking.status", booking_id, {"status": request.status.value})
    return booking.model_dump(mode="json")


@app.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, request: CancelRequest) -> dict[str, Any]:
    action = "booking:update" if request.actor_role in {Role.ADMIN, Role.OPERATOR} else "booking:extend:own"
    _assert_permission(request.actor_role, action)
    booking = bookings.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = BookingStatus.CANCELLED
    if spot_to_booking.get(booking.spot_id) == booking.booking_id:
        spot_to_booking.pop(booking.spot_id, None)
    return booking.model_dump(mode="json")


@app.get("/spots/{spot_id}/active-booking")
async def get_active_booking_for_spot(spot_id: str) -> dict[str, Any]:
    booking_id = spot_to_booking.get(spot_id)
    if not booking_id:
        raise HTTPException(status_code=404, detail="No booking for spot")
    booking = bookings.get(booking_id)
    if booking is None or booking.status not in {BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.ACTIVE}:
        raise HTTPException(status_code=404, detail="No active booking for spot")
    return booking.model_dump(mode="json")


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

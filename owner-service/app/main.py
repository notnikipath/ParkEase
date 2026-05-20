from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.parkease_common import (
    OwnerEvent,
    Role,
    Settings,
    TariffUpdateRequest,
    build_audit_event,
    has_permission,
    occupancy_rate,
)

settings = Settings(service_name="owner-service", service_port=8404)
app = FastAPI(title="ParkEase Owner Service", version="1.0.0")

owner_parkings: dict[str, list[str]] = {
    "OWNER-100": ["PARK-CENTER-01"],
    "OWNER-244": ["PARK-PRIVATE-11"],
    "CITY-MSK": ["PARK-STREET-07"],
}

parking_profiles: dict[str, dict[str, Any]] = {
    "PARK-CENTER-01": {
        "name": "Center Multilevel",
        "total_spots": 540,
        "free_spots": 146,
        "base_price_per_hour": 190,
        "peak_multiplier": 1.1,
        "hourly_load": [0.55, 0.62, 0.71, 0.67, 0.58],
    },
    "PARK-STREET-07": {
        "name": "Arbat Street Zone",
        "total_spots": 120,
        "free_spots": 29,
        "base_price_per_hour": 120,
        "peak_multiplier": 1.05,
        "hourly_load": [0.61, 0.67, 0.73, 0.69, 0.6],
    },
    "PARK-PRIVATE-11": {
        "name": "Private Courtyard 11",
        "total_spots": 44,
        "free_spots": 11,
        "base_price_per_hour": 240,
        "peak_multiplier": 1.2,
        "hourly_load": [0.5, 0.57, 0.64, 0.59, 0.53],
    },
}

owner_events: list[OwnerEvent] = []
audit_log: list[dict[str, Any]] = []


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="owner",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/owners/{owner_id}/parkings")
async def owner_parking_list(owner_id: str, actor_role: Role = Role.OWNER) -> dict[str, Any]:
    _assert_permission(actor_role, "owner:read")
    parking_ids = owner_parkings.get(owner_id, [])
    items = [
        {"parking_id": parking_id, **parking_profiles[parking_id]}
        for parking_id in parking_ids
        if parking_id in parking_profiles
    ]
    return {"owner_id": owner_id, "items": items, "count": len(items)}


@app.post("/owners/{owner_id}/parkings/{parking_id}/tariff")
async def update_tariff(owner_id: str, parking_id: str, request: TariffUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "owner:update_tariff")
    profile = parking_profiles.get(parking_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Parking not found")
    profile["base_price_per_hour"] = request.base_price_per_hour
    profile["peak_multiplier"] = request.peak_multiplier

    event = OwnerEvent(
        event_id=str(uuid4()),
        parking_id=parking_id,
        actor_id=owner_id,
        action="tariff.update",
        details={"base_price_per_hour": request.base_price_per_hour, "peak_multiplier": request.peak_multiplier},
    )
    owner_events.append(event)
    _audit(owner_id, request.actor_role, "owner.tariff.update", parking_id, event.details)
    return {"parking_id": parking_id, "profile": profile}


@app.get("/owners/{owner_id}/parkings/{parking_id}/stats")
async def parking_stats(owner_id: str, parking_id: str, actor_role: Role = Role.OWNER) -> dict[str, Any]:
    _assert_permission(actor_role, "owner:read")
    profile = parking_profiles.get(parking_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Parking not found")
    rate = occupancy_rate(profile["total_spots"], profile["free_spots"])
    revenue_estimate = round(profile["base_price_per_hour"] * profile["total_spots"] * rate * 0.62, 2)
    return {
        "owner_id": owner_id,
        "parking_id": parking_id,
        "occupancy_rate": rate,
        "hourly_load": profile["hourly_load"],
        "revenue_estimate": revenue_estimate,
        "base_price_per_hour": profile["base_price_per_hour"],
    }


@app.get("/owners/{owner_id}/events")
async def owner_event_feed(owner_id: str) -> dict[str, Any]:
    items = [event.model_dump(mode="json") for event in owner_events]
    return {"owner_id": owner_id, "items": items, "count": len(items)}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

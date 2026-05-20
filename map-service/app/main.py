from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.parkease_common import (
    GeoPoint,
    MapSearchRequest,
    ParkingFacility,
    ParkingType,
    Role,
    Settings,
    SpotStatus,
    calculate_dynamic_price,
    choose_best_spot,
    forecast_peak_load,
    has_permission,
    haversine_distance_km,
)

settings = Settings(service_name="map-service", service_port=8405)
app = FastAPI(title="ParkEase Map Service", version="1.0.0")


class FreeSpotsUpdateRequest(BaseModel):
    free_spots: int = Field(ge=0)
    actor_id: str
    actor_role: Role


class SpotSyncRequest(BaseModel):
    spot_id: str
    status: SpotStatus
    actor_id: str
    actor_role: Role


facilities: dict[str, ParkingFacility] = {
    "PARK-CENTER-01": ParkingFacility(
        parking_id="PARK-CENTER-01",
        name="Center Multilevel",
        parking_type=ParkingType.MULTILEVEL,
        address="12 Tverskaya St",
        location=GeoPoint(lat=55.7601, lon=37.6156),
        total_spots=540,
        free_spots=146,
        base_price_per_hour=190,
        owner_id="OWNER-100",
        supports_ev=True,
        indoor=True,
    ),
    "PARK-STREET-07": ParkingFacility(
        parking_id="PARK-STREET-07",
        name="Arbat Street Zone",
        parking_type=ParkingType.STREET,
        address="18 Arbat St",
        location=GeoPoint(lat=55.7520, lon=37.5929),
        total_spots=120,
        free_spots=29,
        base_price_per_hour=120,
        owner_id="CITY-MSK",
    ),
    "PARK-PRIVATE-11": ParkingFacility(
        parking_id="PARK-PRIVATE-11",
        name="Private Courtyard 11",
        parking_type=ParkingType.PRIVATE,
        address="11 Presnensky Val",
        location=GeoPoint(lat=55.7668, lon=37.5634),
        total_spots=44,
        free_spots=11,
        base_price_per_hour=240,
        owner_id="OWNER-244",
        supports_ev=True,
    ),
}

occupancy_history: dict[str, list[float]] = {
    parking_id: [0.48, 0.52, 0.58, 0.63, 0.59] for parking_id in facilities
}

spot_status: dict[str, SpotStatus] = {
    "SPOT-C1-001": SpotStatus.FREE,
    "SPOT-C1-002": SpotStatus.OCCUPIED,
    "SPOT-A7-014": SpotStatus.FREE,
    "SPOT-P11-006": SpotStatus.RESERVED,
}


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/parkings")
async def list_parkings(parking_type: ParkingType | None = None) -> dict[str, Any]:
    items = []
    for facility in facilities.values():
        if parking_type and facility.parking_type != parking_type:
            continue
        occupancy = 1 - (facility.free_spots / facility.total_spots)
        price = calculate_dynamic_price(facility.base_price_per_hour, occupancy, peak_multiplier=1.05)
        payload = facility.model_dump(mode="json")
        payload["dynamic_price_per_hour"] = price
        items.append(payload)
    return {"items": items, "count": len(items)}


@app.post("/parkings/search")
async def search_parkings(request: MapSearchRequest) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for facility in facilities.values():
        if request.parking_type and facility.parking_type != request.parking_type:
            continue
        if facility.free_spots <= 0:
            continue
        distance_km = haversine_distance_km(
            request.user_location.lat,
            request.user_location.lon,
            facility.location.lat,
            facility.location.lon,
        )
        if distance_km > request.radius_km:
            continue
        occupancy = 1 - (facility.free_spots / facility.total_spots)
        price = calculate_dynamic_price(facility.base_price_per_hour, occupancy, peak_multiplier=1.1)
        if request.max_price_per_hour is not None and price > request.max_price_per_hour:
            continue
        candidates.append(
            {
                "parking_id": facility.parking_id,
                "name": facility.name,
                "address": facility.address,
                "parking_type": facility.parking_type.value,
                "distance_km": distance_km,
                "price_per_hour": price,
                "free_spots": facility.free_spots,
                "location": facility.location.model_dump(mode="json"),
                "predicted_peak_load": forecast_peak_load(occupancy_history.get(facility.parking_id, [])),
            }
        )

    best = choose_best_spot(candidates)
    return {"items": sorted(candidates, key=lambda item: (item["distance_km"], item["price_per_hour"])), "best": best}


@app.get("/parkings/{parking_id}")
async def get_parking(parking_id: str) -> dict[str, Any]:
    facility = facilities.get(parking_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Parking not found")
    return facility.model_dump(mode="json")


@app.post("/parkings/{parking_id}/free-spots")
async def update_free_spots(parking_id: str, request: FreeSpotsUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "map:write")
    facility = facilities.get(parking_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Parking not found")
    facility.free_spots = min(request.free_spots, facility.total_spots)
    occupancy = 1 - (facility.free_spots / facility.total_spots)
    occupancy_history.setdefault(parking_id, []).append(round(occupancy, 3))
    occupancy_history[parking_id] = occupancy_history[parking_id][-200:]
    return facility.model_dump(mode="json")


@app.post("/spots/sync")
async def sync_spot_status(request: SpotSyncRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "map:write")
    spot_status[request.spot_id] = request.status
    return {
        "spot_id": request.spot_id,
        "status": request.status,
        "synced_at": datetime.now(UTC),
    }


@app.get("/maps/cache/plan")
async def map_cache_plan(regions: str = "center,north,south") -> dict[str, Any]:
    region_list = [region.strip() for region in regions.split(",") if region.strip()]
    return {
        "provider_primary": settings.maps_provider_url,
        "provider_secondary": settings.mapbox_api_url,
        "priority_regions": region_list[:3],
        "cached_layers": ["parking_polygons", "road_graph", "indoor_levels"],
    }

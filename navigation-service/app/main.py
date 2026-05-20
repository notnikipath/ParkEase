from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.parkease_common import (
    GeoPoint,
    NavigationRoute,
    Role,
    Settings,
    estimate_drive_eta_minutes,
    has_permission,
    haversine_distance_km,
)

settings = Settings(service_name="navigation-service", service_port=8402)
app = FastAPI(title="ParkEase Navigation Service", version="1.0.0")

routes: dict[str, NavigationRoute] = {}

parking_locations: dict[str, GeoPoint] = {
    "PARK-CENTER-01": GeoPoint(lat=55.7601, lon=37.6156),
    "PARK-STREET-07": GeoPoint(lat=55.7520, lon=37.5929),
    "PARK-PRIVATE-11": GeoPoint(lat=55.7668, lon=37.5634),
}


class BuildRouteRequest(BaseModel):
    parking_id: str
    spot_id: str
    from_location: GeoPoint
    traffic_index: float = Field(default=0.3, ge=0, le=1)
    actor_role: Role = Role.CLIENT


BuildRouteRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/routes/build")
async def build_route(request: BuildRouteRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "navigation:read")
    destination = parking_locations.get(request.parking_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Parking location not found")

    distance_km = haversine_distance_km(
        request.from_location.lat,
        request.from_location.lon,
        destination.lat,
        destination.lon,
    )
    eta_minutes = estimate_drive_eta_minutes(distance_km, request.traffic_index)

    route = NavigationRoute(
        route_id=str(uuid4()),
        parking_id=request.parking_id,
        spot_id=request.spot_id,
        from_location=request.from_location,
        to_location=destination,
        distance_km=max(distance_km, 0.1),
        eta_minutes=eta_minutes,
        steps=[
            "Head to the nearest arterial road",
            "Follow live traffic guidance to parking entry gate",
            "Use lane guidance for designated parking sector",
        ],
        indoor_path=[
            "Enter via gate A",
            "Drive to level 2",
            f"Follow blue signs to {request.spot_id}",
        ],
    )
    routes[route.route_id] = route
    return route.model_dump(mode="json")


@app.get("/routes/{route_id}")
async def get_route(route_id: str) -> dict[str, Any]:
    route = routes.get(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route.model_dump(mode="json")


@app.get("/indoor/{parking_id}/{spot_id}")
async def indoor_navigation(parking_id: str, spot_id: str) -> dict[str, Any]:
    if parking_id not in parking_locations:
        raise HTTPException(status_code=404, detail="Parking not found")
    return {
        "parking_id": parking_id,
        "spot_id": spot_id,
        "ar_overlay_hint": "Turn right in 15 meters and follow sector C arrows.",
        "steps": [
            "Pass checkpoint",
            "Take ramp to level 2",
            f"Stop at {spot_id}",
        ],
    }


@app.get("/routes")
async def list_routes(parking_id: str | None = None) -> dict[str, Any]:
    items = []
    for route in routes.values():
        if parking_id and route.parking_id != parking_id:
            continue
        items.append(route.model_dump(mode="json"))
    return {"items": items, "count": len(items)}

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.parkease_common import FindAndBookWorkflowResult, GeoPoint, Role, Settings, sign_token, verify_token


class GatewaySettings(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8400

    booking_service_url: str = "http://booking-service:8401"
    navigation_service_url: str = "http://navigation-service:8402"
    sensor_service_url: str = "http://sensor-service:8403"
    owner_service_url: str = "http://owner-service:8404"
    map_service_url: str = "http://map-service:8405"
    analytics_service_url: str = "http://analytics-service:8406"
    notification_service_url: str = "http://notification-service:8407"
    payment_service_url: str = "http://payment-service:8408"

    jwt_secret: str = Settings().jwt_secret
    token_exp_minutes: int = 240

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = GatewaySettings()
app = FastAPI(title="ParkEase API Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    user_id: str
    role: Role
    language: str = Field(default="ru", pattern="^(ru|en)$")


class FindAndBookRequest(BaseModel):
    user_id: str
    location: GeoPoint
    duration_minutes: int = Field(gt=0, le=24 * 60)
    plate_number: str
    radius_km: float = Field(default=3.0, gt=0, le=30)
    max_price_per_hour: float | None = Field(default=None, ge=0)


class ExtendBookingWorkflowRequest(BaseModel):
    booking_id: str
    extra_minutes: int = Field(gt=0, le=12 * 60)
    user_id: str


AuthRequest.model_rebuild()
FindAndBookRequest.model_rebuild()
ExtendBookingWorkflowRequest.model_rebuild()


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


def _service_urls() -> dict[str, str]:
    return {
        "booking": settings.booking_service_url,
        "navigation": settings.navigation_service_url,
        "sensor": settings.sensor_service_url,
        "owner": settings.owner_service_url,
        "map": settings.map_service_url,
        "analytics": settings.analytics_service_url,
        "notification": settings.notification_service_url,
        "payment": settings.payment_service_url,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/token")
async def issue_token(request: AuthRequest) -> dict[str, str]:
    token = sign_token(
        {"sub": request.user_id, "role": request.role.value, "language": request.language},
        settings.jwt_secret,
        exp_minutes=settings.token_exp_minutes,
    )
    return {"access_token": token, "token_type": "Bearer"}


@app.post("/auth/verify")
async def verify_auth(token: str) -> dict[str, Any]:
    payload = verify_token(token, settings.jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/services/health")
async def service_health() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, base_url in _service_urls().items():
            try:
                statuses[name] = await _get_json(client, f"{base_url}/health")
            except HTTPException as exc:
                statuses[name] = {"status": "error", "detail": exc.detail}
            except httpx.HTTPError as exc:
                statuses[name] = {"status": "error", "detail": str(exc)}
    return statuses


@app.post("/workflow/find-and-book")
async def find_and_book_workflow(request: FindAndBookRequest) -> dict[str, Any]:
    started = perf_counter()
    async with httpx.AsyncClient(timeout=25.0) as client:
        search_result = await _post_json(
            client,
            f"{settings.map_service_url}/parkings/search",
            {
                "user_location": request.location.model_dump(mode="json"),
                "radius_km": request.radius_km,
                "max_price_per_hour": request.max_price_per_hour,
            },
        )
        if not search_result["items"]:
            raise HTTPException(status_code=404, detail="No free parking found")

        selected_parking = search_result.get("best") or search_result["items"][0]
        spot_candidates = await _get_json(
            client,
            f"{settings.sensor_service_url}/spots",
            {"parking_id": selected_parking["parking_id"], "status": "free"},
        )
        if not spot_candidates["items"]:
            raise HTTPException(status_code=409, detail="Parking has no currently free sensor spots")

        selected_spot = spot_candidates["items"][0]
        booking = await _post_json(
            client,
            f"{settings.booking_service_url}/bookings",
            {
                "user_id": request.user_id,
                "parking_id": selected_parking["parking_id"],
                "spot_id": selected_spot["spot_id"],
                "duration_minutes": request.duration_minutes,
                "plate_number": request.plate_number,
                "actor_role": Role.CLIENT.value,
            },
        )

        payment = await _post_json(
            client,
            f"{settings.payment_service_url}/payments/charge",
            {
                "booking_id": booking["booking_id"],
                "amount": booking["total_price"],
                "payment_method": "card",
                "actor_role": Role.CLIENT.value,
            },
        )

        await _post_json(
            client,
            f"{settings.booking_service_url}/bookings/{booking['booking_id']}/status",
            {
                "status": "confirmed",
                "actor_id": "OP-001",
                "actor_role": Role.ADMIN.value,
            },
        )

        reservation = await _post_json(
            client,
            f"{settings.sensor_service_url}/spots/{selected_spot['spot_id']}/reserve",
            {
                "booking_id": booking["booking_id"],
                "plate_number": request.plate_number,
                "actor_id": "OP-001",
                "actor_role": Role.ADMIN.value,
            },
        )

        route = await _post_json(
            client,
            f"{settings.navigation_service_url}/routes/build",
            {
                "parking_id": selected_parking["parking_id"],
                "spot_id": selected_spot["spot_id"],
                "from_location": request.location.model_dump(mode="json"),
                "traffic_index": 0.32,
                "actor_role": Role.CLIENT.value,
            },
        )

        await _post_json(
            client,
            f"{settings.notification_service_url}/notify/booking-confirmed",
            {
                "user_id": request.user_id,
                "booking_id": booking["booking_id"],
                "spot_id": selected_spot["spot_id"],
                "parking_id": selected_parking["parking_id"],
                "actor_role": Role.OPERATOR.value,
            },
        )

        elapsed = perf_counter() - started
        await _post_json(
            client,
            f"{settings.analytics_service_url}/analytics/ingest/booking",
            {
                "booking_id": booking["booking_id"],
                "parking_id": selected_parking["parking_id"],
                "booking_latency_seconds": round(elapsed, 3),
                "status_update_latency_seconds": 1.8,
                "occupancy_ratio": min(0.95, max(0.0, 1 - selected_parking["free_spots"] / 200)),
            },
        )
        await _post_json(
            client,
            f"{settings.analytics_service_url}/analytics/ingest/payment",
            {
                "payment_id": payment["payment_id"],
                "parking_id": selected_parking["parking_id"],
                "amount": payment["amount"],
            },
        )

    result = FindAndBookWorkflowResult(
        selected_spot=selected_spot,
        booking=booking,
        payment=payment,
        reservation=reservation,
        route=route,
    )
    payload = result.model_dump(mode="json")
    payload["latency_seconds"] = round(perf_counter() - started, 3)
    return payload


@app.post("/workflow/extend-booking")
async def extend_booking_workflow(request: ExtendBookingWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        booking = await _post_json(
            client,
            f"{settings.booking_service_url}/bookings/{request.booking_id}/extend",
            {
                "extra_minutes": request.extra_minutes,
                "actor_role": Role.CLIENT.value,
            },
        )
        amount = round(booking["rate_per_hour"] * request.extra_minutes / 60, 2)
        payment = await _post_json(
            client,
            f"{settings.payment_service_url}/payments/auto-charge",
            {
                "booking_id": request.booking_id,
                "amount": amount,
                "geofence_trigger": True,
                "actor_role": Role.CLIENT.value,
            },
        )
    return {"booking": booking, "extra_payment": payment}


@app.get("/dashboard/{parking_id}")
async def parking_dashboard(parking_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        parking = await _get_json(client, f"{settings.map_service_url}/parkings/{parking_id}")
        spots = await _get_json(client, f"{settings.sensor_service_url}/spots", {"parking_id": parking_id})
        analytics_kpi = await _get_json(client, f"{settings.analytics_service_url}/analytics/kpi")
        revenue = await _get_json(
            client,
            f"{settings.analytics_service_url}/analytics/revenue",
            {"parking_id": parking_id},
        )
        hourly_load = await _get_json(
            client,
            f"{settings.analytics_service_url}/analytics/load/hourly",
            {"parking_id": parking_id},
        )
        notifications = await _get_json(client, f"{settings.notification_service_url}/notify/history")
    return {
        "parking": parking,
        "spots": spots,
        "analytics_kpi": analytics_kpi,
        "revenue": revenue,
        "hourly_load": hourly_load,
        "notifications": notifications,
    }

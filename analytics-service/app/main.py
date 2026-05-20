from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.parkease_common import (
    Role,
    Settings,
    average_booking_time_seconds,
    forecast_peak_load,
    has_permission,
    revenue_total,
    sharding_plan,
)

settings = Settings(service_name="analytics-service", service_port=8406)
app = FastAPI(title="ParkEase Analytics Service", version="1.0.0")

booking_latency_samples: list[float] = [1.42, 1.67, 1.51, 1.58]
status_update_latency_samples: list[float] = [2.1, 2.7, 3.0, 2.4]
payments: list[float] = [320.0, 540.0, 210.0, 460.0]
occupancy_by_hour: dict[int, float] = {
    8: 0.41,
    9: 0.57,
    10: 0.63,
    11: 0.68,
    12: 0.71,
    13: 0.75,
    14: 0.73,
    15: 0.7,
    16: 0.67,
    17: 0.74,
    18: 0.79,
    19: 0.76,
}
parking_revenue: dict[str, float] = {
    "PARK-CENTER-01": 178340.0,
    "PARK-STREET-07": 92300.0,
    "PARK-PRIVATE-11": 61480.0,
}


class BookingAnalyticsIngestRequest(BaseModel):
    booking_id: str
    parking_id: str
    booking_latency_seconds: float = Field(gt=0)
    status_update_latency_seconds: float = Field(gt=0)
    occupancy_ratio: float = Field(ge=0, le=1)


class PaymentAnalyticsIngestRequest(BaseModel):
    payment_id: str
    parking_id: str
    amount: float = Field(ge=0)


BookingAnalyticsIngestRequest.model_rebuild()
PaymentAnalyticsIngestRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/analytics/ingest/booking")
async def ingest_booking(request: BookingAnalyticsIngestRequest) -> dict[str, Any]:
    booking_latency_samples.append(request.booking_latency_seconds)
    status_update_latency_samples.append(request.status_update_latency_seconds)
    current_hour = datetime.now(UTC).hour
    occupancy_by_hour[current_hour] = request.occupancy_ratio
    return {"status": "accepted", "booking_id": request.booking_id}


@app.post("/analytics/ingest/payment")
async def ingest_payment(request: PaymentAnalyticsIngestRequest) -> dict[str, Any]:
    payments.append(request.amount)
    parking_revenue[request.parking_id] = round(parking_revenue.get(request.parking_id, 0) + request.amount, 2)
    return {"status": "accepted", "payment_id": request.payment_id}


@app.get("/analytics/load/hourly")
async def hourly_load(parking_id: str | None = None) -> dict[str, Any]:
    _ = parking_id
    items = [{"hour": hour, "occupancy_ratio": value} for hour, value in sorted(occupancy_by_hour.items())]
    return {"items": items, "count": len(items)}


@app.get("/analytics/revenue")
async def revenue(parking_id: str | None = None) -> dict[str, Any]:
    if parking_id:
        return {"parking_id": parking_id, "revenue": parking_revenue.get(parking_id, 0.0)}
    return {
        "total": revenue_total(payments),
        "by_parking": parking_revenue,
    }


@app.get("/analytics/forecast")
async def forecast() -> dict[str, Any]:
    history = [occupancy_by_hour[hour] for hour in sorted(occupancy_by_hour)]
    return {
        "forecast_peak_load": forecast_peak_load(history),
        "recommendation": "Increase price by 8% during 17:00-20:00",
    }


@app.get("/analytics/kpi")
async def kpi() -> dict[str, Any]:
    booking_avg = average_booking_time_seconds(booking_latency_samples)
    status_avg = average_booking_time_seconds(status_update_latency_samples)
    return {
        "booking_time_seconds_avg": booking_avg,
        "booking_target_seconds": settings.booking_target_seconds,
        "status_update_seconds_avg": status_avg,
        "status_update_target_seconds": settings.spot_status_update_target_seconds,
        "supported_spots_target": settings.supported_spots_target,
        "supports_target_booking": booking_avg <= settings.booking_target_seconds,
        "supports_target_status": status_avg <= settings.spot_status_update_target_seconds,
    }


@app.get("/analytics/sharding/plan")
async def shard_plan(total_spots: int = 100000, districts: int = 16) -> dict[str, Any]:
    return sharding_plan(total_spots, districts)


@app.get("/dashboards/{role}")
async def dashboard(role: Role) -> dict[str, Any]:
    _assert_permission(role, "analytics:read")
    return {
        "role": role.value,
        "widgets": ["hourly_load", "revenue", "forecast", "kpi"],
        "kpi": await kpi(),
    }

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.parkease_common import NotificationChannel, Role, Settings, Severity, has_permission

settings = Settings(service_name="notification-service", service_port=8407)
app = FastAPI(title="ParkEase Notification Service", version="1.0.0")

messages: list[dict[str, Any]] = []


class NotificationRequest(BaseModel):
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    severity: Severity = Severity.INFO
    actor_role: Role


class BookingNotificationRequest(BaseModel):
    user_id: str
    booking_id: str
    spot_id: str
    parking_id: str
    actor_role: Role


class TelegramBookingRequest(BaseModel):
    chat_id: str
    booking_id: str
    parking_id: str
    spot_id: str


NotificationRequest.model_rebuild()
BookingNotificationRequest.model_rebuild()
TelegramBookingRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/notify/send")
async def send_notification(request: NotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = request.model_dump(mode="json")
    payload["status"] = "queued"
    messages.append(payload)
    return payload


@app.post("/notify/booking-confirmed")
async def booking_confirmed(request: BookingNotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": NotificationChannel.PUSH.value,
        "recipient": request.user_id,
        "subject": f"Booking {request.booking_id} confirmed",
        "body": f"Spot {request.spot_id} at {request.parking_id} is reserved for you.",
        "severity": Severity.INFO.value,
        "status": "queued",
    }
    messages.append(payload)
    return payload


@app.post("/notify/telegram-booking")
async def telegram_booking(request: TelegramBookingRequest) -> dict[str, Any]:
    payload = {
        "channel": NotificationChannel.TELEGRAM.value,
        "recipient": request.chat_id,
        "subject": "Telegram booking",
        "body": f"Booking {request.booking_id}: {request.parking_id}/{request.spot_id}",
        "severity": Severity.INFO.value,
        "status": "sent",
    }
    messages.append(payload)
    return payload


@app.get("/notify/history")
async def history() -> dict[str, Any]:
    return {"items": messages, "count": len(messages)}

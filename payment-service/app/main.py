from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.parkease_common import (
    PaymentChargeRequest,
    PaymentRecord,
    PaymentStatus,
    Role,
    Settings,
    build_audit_event,
    has_permission,
)

settings = Settings(service_name="payment-service", service_port=8408)
app = FastAPI(title="ParkEase Payment Service", version="1.0.0")

payments: dict[str, PaymentRecord] = {}
booking_index: dict[str, str] = {}
audit_log: list[dict[str, Any]] = []


class PaymentStatusUpdateRequest(BaseModel):
    status: PaymentStatus
    actor_id: str
    actor_role: Role


class AutoChargeRequest(BaseModel):
    booking_id: str
    amount: float = Field(gt=0)
    geofence_trigger: bool = True
    actor_role: Role = Role.CLIENT


PaymentStatusUpdateRequest.model_rebuild()
AutoChargeRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="payment",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/payments/charge")
async def charge(request: PaymentChargeRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "payment:pay")
    payment = PaymentRecord(
        payment_id=str(uuid4()),
        booking_id=request.booking_id,
        amount=request.amount,
        payment_method=request.payment_method,
        status=PaymentStatus.PAID,
        transaction_ref=f"TX-{uuid4().hex[:10].upper()}",
    )
    payments[payment.payment_id] = payment
    booking_index[request.booking_id] = payment.payment_id
    _audit(request.booking_id, request.actor_role, "payment.charge", payment.payment_id, {"amount": request.amount})
    return payment.model_dump(mode="json")


@app.post("/payments/auto-charge")
async def auto_charge(request: AutoChargeRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "payment:pay")
    method = "auto_geo" if request.geofence_trigger else "card"
    payment = PaymentRecord(
        payment_id=str(uuid4()),
        booking_id=request.booking_id,
        amount=request.amount,
        payment_method=method,
        status=PaymentStatus.PAID,
        transaction_ref=f"AUTO-{uuid4().hex[:8].upper()}",
    )
    payments[payment.payment_id] = payment
    booking_index[request.booking_id] = payment.payment_id
    return payment.model_dump(mode="json")


@app.get("/payments/{payment_id}")
async def get_payment(payment_id: str) -> dict[str, Any]:
    payment = payments.get(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment.model_dump(mode="json")


@app.get("/payments/by-booking/{booking_id}")
async def payment_by_booking(booking_id: str) -> dict[str, Any]:
    payment_id = booking_index.get(booking_id)
    if payment_id is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment = payments[payment_id]
    return payment.model_dump(mode="json")


@app.get("/payments")
async def list_payments(status: PaymentStatus | None = None) -> dict[str, Any]:
    items = []
    for payment in payments.values():
        if status and payment.status != status:
            continue
        items.append(payment.model_dump(mode="json"))
    return {"items": items, "count": len(items)}


@app.post("/payments/{payment_id}/status")
async def set_status(payment_id: str, request: PaymentStatusUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "payment:read")
    payment = payments.get(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment.status = request.status
    _audit(request.actor_id, request.actor_role, "payment.status", payment_id, {"status": request.status.value})
    return payment.model_dump(mode="json")


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}

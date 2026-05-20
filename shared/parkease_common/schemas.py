from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ParkingType(str, Enum):
    STREET = "street"
    MULTILEVEL = "multilevel"
    PRIVATE = "private"


class SpotStatus(str, Enum):
    FREE = "free"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    BLOCKED = "blocked"


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentStatus(str, Enum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class SensorEventType(str, Enum):
    OCCUPANCY = "occupancy"
    PLATE_DETECTED = "plate_detected"
    ENTRY = "entry"
    EXIT = "exit"


class NotificationChannel(str, Enum):
    PUSH = "push"
    SMS = "sms"
    EMAIL = "email"
    TELEGRAM = "telegram"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Role(str, Enum):
    CLIENT = "client"
    OWNER = "owner"
    OPERATOR = "operator"
    ADMIN = "admin"


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ParkingFacility(BaseModel):
    parking_id: str
    name: str
    parking_type: ParkingType
    address: str
    location: GeoPoint
    total_spots: int = Field(gt=0)
    free_spots: int = Field(ge=0)
    base_price_per_hour: float = Field(ge=0)
    owner_id: str
    supports_ev: bool = False
    indoor: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ParkingSpot(BaseModel):
    spot_id: str
    parking_id: str
    parking_type: ParkingType
    status: SpotStatus = SpotStatus.FREE
    level: int = 0
    has_charger: bool = False
    plate_number: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MapSearchRequest(BaseModel):
    user_location: GeoPoint
    radius_km: float = Field(default=3.0, gt=0, le=30)
    parking_type: ParkingType | None = None
    max_price_per_hour: float | None = Field(default=None, ge=0)


class BookingCreateRequest(BaseModel):
    user_id: str
    parking_id: str
    spot_id: str
    duration_minutes: int = Field(gt=0, le=24 * 60)
    plate_number: str
    actor_role: Role = Role.CLIENT


class BookingExtendRequest(BaseModel):
    extra_minutes: int = Field(gt=0, le=12 * 60)
    actor_role: Role


class BookingRecord(BaseModel):
    booking_id: str
    user_id: str
    parking_id: str
    spot_id: str
    plate_number: str
    start_at: datetime
    end_at: datetime
    reserved_until: datetime
    rate_per_hour: float = Field(ge=0)
    total_price: float = Field(ge=0)
    status: BookingStatus = BookingStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaymentChargeRequest(BaseModel):
    booking_id: str
    amount: float = Field(gt=0)
    payment_method: str = "card"
    actor_role: Role = Role.CLIENT


class PaymentRecord(BaseModel):
    payment_id: str
    booking_id: str
    amount: float = Field(ge=0)
    payment_method: str
    status: PaymentStatus
    transaction_ref: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SensorEvent(BaseModel):
    event_id: str
    spot_id: str
    parking_id: str
    event_type: SensorEventType
    occupied: bool | None = None
    plate_number: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: str = "sensor"
    event_time: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SensorBatch(BaseModel):
    events: list[SensorEvent] = Field(default_factory=list)
    actor_role: Role = Role.OPERATOR


class NavigationRoute(BaseModel):
    route_id: str
    parking_id: str
    spot_id: str
    from_location: GeoPoint
    to_location: GeoPoint
    distance_km: float = Field(gt=0)
    eta_minutes: int = Field(gt=0)
    steps: list[str] = Field(default_factory=list)
    indoor_path: list[str] = Field(default_factory=list)


class TariffUpdateRequest(BaseModel):
    base_price_per_hour: float = Field(ge=0)
    peak_multiplier: float = Field(default=1.0, ge=0.5, le=3.0)
    actor_role: Role


class OwnerEvent(BaseModel):
    event_id: str
    parking_id: str
    actor_id: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IntegrationSyncRequest(BaseModel):
    system_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    actor_id: str
    actor_role: Role


class IntegrationSyncResult(BaseModel):
    sync_id: str
    system_name: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(BaseModel):
    event_id: str
    actor_id: str
    actor_role: Role | str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FindAndBookWorkflowResult(BaseModel):
    selected_spot: dict[str, Any]
    booking: dict[str, Any]
    payment: dict[str, Any]
    reservation: dict[str, Any]
    route: dict[str, Any]
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

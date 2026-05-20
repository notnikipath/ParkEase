from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]

booking_module = load_module("booking_module", ROOT / "booking-service" / "app" / "main.py")
navigation_module = load_module("navigation_module", ROOT / "navigation-service" / "app" / "main.py")
sensor_module = load_module("sensor_module", ROOT / "sensor-service" / "app" / "main.py")
owner_module = load_module("owner_module", ROOT / "owner-service" / "app" / "main.py")
map_module = load_module("map_module", ROOT / "map-service" / "app" / "main.py")
analytics_module = load_module("analytics_module", ROOT / "analytics-service" / "app" / "main.py")
notification_module = load_module("notification_module", ROOT / "notification-service" / "app" / "main.py")
payment_module = load_module("payment_module", ROOT / "payment-service" / "app" / "main.py")

booking_client = TestClient(booking_module.app)
navigation_client = TestClient(navigation_module.app)
sensor_client = TestClient(sensor_module.app)
owner_client = TestClient(owner_module.app)
map_client = TestClient(map_module.app)
analytics_client = TestClient(analytics_module.app)
notification_client = TestClient(notification_module.app)
payment_client = TestClient(payment_module.app)


def test_find_book_pay_and_navigate_flow() -> None:
    search = map_client.post(
        "/parkings/search",
        json={
            "user_location": {"lat": 55.758, "lon": 37.615},
            "radius_km": 5,
        },
    )
    assert search.status_code == 200
    items = search.json()["items"]
    assert items
    parking = items[0]

    spots = sensor_client.get("/spots", params={"parking_id": parking["parking_id"], "status": "free"})
    assert spots.status_code == 200
    spot = spots.json()["items"][0]

    booking = booking_client.post(
        "/bookings",
        json={
            "user_id": "USR-100",
            "parking_id": parking["parking_id"],
            "spot_id": spot["spot_id"],
            "duration_minutes": 90,
            "plate_number": "X123YY77",
            "actor_role": "client",
        },
    )
    assert booking.status_code == 200
    booking_data = booking.json()

    payment = payment_client.post(
        "/payments/charge",
        json={
            "booking_id": booking_data["booking_id"],
            "amount": booking_data["total_price"],
            "payment_method": "card",
            "actor_role": "client",
        },
    )
    assert payment.status_code == 200
    payment_data = payment.json()

    reserve = sensor_client.post(
        f"/spots/{spot['spot_id']}/reserve",
        json={
            "booking_id": booking_data["booking_id"],
            "plate_number": "X123YY77",
            "actor_id": "ADM-1",
            "actor_role": "admin",
        },
    )
    assert reserve.status_code == 200
    assert reserve.json()["status"] == "reserved"

    route = navigation_client.post(
        "/routes/build",
        json={
            "parking_id": parking["parking_id"],
            "spot_id": spot["spot_id"],
            "from_location": {"lat": 55.758, "lon": 37.615},
            "traffic_index": 0.35,
            "actor_role": "client",
        },
    )
    assert route.status_code == 200
    assert route.json()["eta_minutes"] > 0

    notice = notification_client.post(
        "/notify/booking-confirmed",
        json={
            "user_id": "USR-100",
            "booking_id": booking_data["booking_id"],
            "spot_id": spot["spot_id"],
            "parking_id": parking["parking_id"],
            "actor_role": "operator",
        },
    )
    assert notice.status_code == 200

    ingest_booking = analytics_client.post(
        "/analytics/ingest/booking",
        json={
            "booking_id": booking_data["booking_id"],
            "parking_id": parking["parking_id"],
            "booking_latency_seconds": 1.8,
            "status_update_latency_seconds": 2.1,
            "occupancy_ratio": 0.72,
        },
    )
    assert ingest_booking.status_code == 200

    ingest_payment = analytics_client.post(
        "/analytics/ingest/payment",
        json={
            "payment_id": payment_data["payment_id"],
            "parking_id": parking["parking_id"],
            "amount": payment_data["amount"],
        },
    )
    assert ingest_payment.status_code == 200


def test_sensor_owner_and_analytics_features() -> None:
    sensor_batch = sensor_client.post(
        "/sensors/ingest",
        json={
            "events": [
                {
                    "event_id": "EV-1",
                    "spot_id": "SPOT-A7-014",
                    "parking_id": "PARK-STREET-07",
                    "event_type": "occupancy",
                    "occupied": True,
                    "source": "sensor",
                }
            ],
            "actor_role": "operator",
        },
    )
    assert sensor_batch.status_code == 200
    assert sensor_batch.json()["accepted"] == 1

    recognize = sensor_client.post(
        "/plates/recognize",
        json={
            "plate_number": "A123BC77",
            "parking_id": "PARK-CENTER-01",
            "confidence": 0.93,
        },
    )
    assert recognize.status_code == 200
    assert recognize.json()["gate_action"] in {"open", "manual_check"}

    tariff = owner_client.post(
        "/owners/OWNER-100/parkings/PARK-CENTER-01/tariff",
        json={
            "base_price_per_hour": 210,
            "peak_multiplier": 1.15,
            "actor_role": "owner",
        },
    )
    assert tariff.status_code == 200

    forecast = analytics_client.get("/analytics/forecast")
    assert forecast.status_code == 200
    assert "forecast_peak_load" in forecast.json()

    kpi = analytics_client.get("/analytics/kpi")
    assert kpi.status_code == 200
    assert "supports_target_booking" in kpi.json()

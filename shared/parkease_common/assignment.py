from __future__ import annotations

from math import acos, cos, radians, sin

from .schemas import Severity


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Fast spherical distance approximation for nearby parking search."""
    lat1r = radians(lat1)
    lon1r = radians(lon1)
    lat2r = radians(lat2)
    lon2r = radians(lon2)
    inner = sin(lat1r) * sin(lat2r) + cos(lat1r) * cos(lat2r) * cos(lon2r - lon1r)
    clamped = min(1.0, max(-1.0, inner))
    return round(6371.0 * acos(clamped), 3)


def estimate_drive_eta_minutes(distance_km: float, traffic_index: float = 0.3) -> int:
    speed_kph = max(8.0, 34.0 * (1 - min(max(traffic_index, 0.0), 1.0) * 0.55))
    minutes = max(1, round((distance_km / speed_kph) * 60))
    return minutes


def calculate_dynamic_price(base_price_per_hour: float, occupancy_ratio: float, peak_multiplier: float = 1.0) -> float:
    normalized_occupancy = min(max(occupancy_ratio, 0.0), 1.0)
    occupancy_factor = 1 + normalized_occupancy * 0.65
    price = base_price_per_hour * occupancy_factor * max(0.5, peak_multiplier)
    return round(price, 2)


def predict_free_spots(total_spots: int, occupancy_history: list[float], event_trend: float = 0.0) -> int:
    if total_spots <= 0:
        return 0
    if not occupancy_history:
        return max(0, round(total_spots * 0.4))
    recent = occupancy_history[-12:]
    avg_occupancy = sum(recent) / len(recent)
    adjusted = min(max(avg_occupancy + event_trend, 0.0), 1.0)
    return max(0, round(total_spots * (1 - adjusted)))


def choose_best_spot(candidates: list[dict[str, float]]) -> dict[str, float] | None:
    if not candidates:
        return None

    def score(item: dict[str, float]) -> float:
        return float(item.get("distance_km", 0)) * 0.55 + float(item.get("price_per_hour", 0)) * 0.45

    return min(candidates, key=score)


def detect_sensor_anomalies(events_per_minute: list[int]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not events_per_minute:
        return findings
    max_rate = max(events_per_minute)
    min_rate = min(events_per_minute)
    if max_rate > 120:
        findings.append(
            {
                "severity": Severity.WARNING.value,
                "code": "high_sensor_rate",
                "message": "Sensor stream spike detected above 120 events per minute.",
            }
        )
    if min_rate == 0 and len(events_per_minute) >= 5:
        findings.append(
            {
                "severity": Severity.CRITICAL.value,
                "code": "sensor_silence",
                "message": "Sensor silence detected in observation window.",
            }
        )
    return findings

from __future__ import annotations


def occupancy_rate(total_spots: int, free_spots: int) -> float:
    if total_spots <= 0:
        return 0.0
    occupied = max(total_spots - max(free_spots, 0), 0)
    return round(min(occupied / total_spots, 1.0), 3)


def average_booking_time_seconds(samples: list[float]) -> float:
    if not samples:
        return 0.0
    return round(sum(samples) / len(samples), 3)


def update_latency_seconds(event_timestamp_ms: int, processed_timestamp_ms: int) -> float:
    return round(max(processed_timestamp_ms - event_timestamp_ms, 0) / 1000, 3)


def revenue_total(payments: list[float]) -> float:
    return round(sum(value for value in payments if value > 0), 2)


def forecast_peak_load(occupancy_history: list[float]) -> float:
    if not occupancy_history:
        return 0.0
    recent = occupancy_history[-24:]
    weighted_sum = 0.0
    weighted_total = 0.0
    for idx, value in enumerate(recent, start=1):
        weighted_sum += idx * min(max(value, 0.0), 1.0)
        weighted_total += idx
    if weighted_total == 0:
        return 0.0
    return round(weighted_sum / weighted_total, 3)


def sharding_plan(total_parking_spots: int, districts: int) -> dict[str, int]:
    shards = max(1, min(64, max(districts, total_parking_spots // 5000)))
    per_shard = max(1, total_parking_spots // shards) if total_parking_spots > 0 else 1
    return {"shards": shards, "spots_per_shard": per_shard}

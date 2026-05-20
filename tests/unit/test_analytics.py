from shared.parkease_common import (
    average_booking_time_seconds,
    forecast_peak_load,
    occupancy_rate,
    revenue_total,
    sharding_plan,
    update_latency_seconds,
)


def test_occupancy_rate() -> None:
    assert occupancy_rate(100, 25) == 0.75


def test_average_booking_time() -> None:
    assert average_booking_time_seconds([1.2, 1.8, 1.5]) == 1.5


def test_update_latency_seconds() -> None:
    assert update_latency_seconds(1_000, 4_500) == 3.5


def test_revenue_total() -> None:
    assert revenue_total([100, 200.5, -10]) == 300.5


def test_forecast_peak_load() -> None:
    value = forecast_peak_load([0.4, 0.5, 0.62, 0.7])
    assert 0 <= value <= 1


def test_sharding_plan() -> None:
    plan = sharding_plan(100_000, 20)
    assert plan["shards"] >= 1
    assert plan["spots_per_shard"] >= 1

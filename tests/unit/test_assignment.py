from shared.parkease_common import (
    calculate_dynamic_price,
    detect_sensor_anomalies,
    estimate_drive_eta_minutes,
    haversine_distance_km,
    predict_free_spots,
)


def test_haversine_distance_positive() -> None:
    distance = haversine_distance_km(55.75, 37.61, 55.76, 37.62)
    assert distance > 0


def test_estimate_drive_eta_reasonable() -> None:
    eta = estimate_drive_eta_minutes(8.5, traffic_index=0.4)
    assert 1 <= eta <= 120


def test_dynamic_price_increases_with_occupancy() -> None:
    low = calculate_dynamic_price(120, occupancy_ratio=0.2, peak_multiplier=1.0)
    high = calculate_dynamic_price(120, occupancy_ratio=0.9, peak_multiplier=1.0)
    assert high > low


def test_predict_free_spots() -> None:
    predicted = predict_free_spots(200, [0.5, 0.52, 0.6, 0.58], event_trend=0.05)
    assert 0 <= predicted <= 200


def test_detect_sensor_anomalies() -> None:
    findings = detect_sensor_anomalies([40, 0, 35, 130, 38])
    codes = {item["code"] for item in findings}
    assert "high_sensor_rate" in codes
    assert "sensor_silence" in codes

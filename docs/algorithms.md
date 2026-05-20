# Algorithms

## 1. Dynamic Pricing

`calculate_dynamic_price(base_price_per_hour, occupancy_ratio, peak_multiplier)`

- Occupancy-aware factor scales price when free spots become scarce.
- Peak multiplier allows owner-configured tariff windows.

## 2. Free Spot Forecast

`predict_free_spots(total_spots, occupancy_history, event_trend)`

- Uses recent occupancy signal and trend correction.
- Returns projected free spots for short horizon decisions.

## 3. Best Spot Selection

`choose_best_spot(candidates)`

- Weighted score uses both distance and price.
- Minimal score is selected as recommended spot.

## 4. ETA Estimation

`estimate_drive_eta_minutes(distance_km, traffic_index)`

- Computes ETA with traffic penalty factor.
- Used in navigation route construction.

## 5. Sensor Anomaly Detection

`detect_sensor_anomalies(events_per_minute)`

- Detects stream spikes and silence windows.
- Helps operations monitor sensor health.

## 6. Analytics KPIs

- `average_booking_time_seconds`
- `update_latency_seconds`
- `forecast_peak_load`
- `sharding_plan`

These functions feed KPI dashboards and capacity planning.

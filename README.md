# ParkEase

ParkEase - microservice platform for smart parking search, reservation, payment, and navigation.

## Project Goal

Build a city-wide platform that helps drivers find free spots, reserve them, pay online, and navigate to the exact place using map + sensor + camera integration.

## Supported Parking Types

- Street parking (`street`)
- Multilevel parking (`multilevel`)
- Private parking for rent (`private`)

## Microservices

```text
parkease/
├── api-gateway/
├── map-service/
├── sensor-service/
├── booking-service/
├── payment-service/
├── navigation-service/
├── owner-service/
├── analytics-service/
└── notification-service/
```

## Core Modules

- Map module: parking map, price, free spots
- Sensors and monitoring module: occupancy sensors, ANPR plate recognition
- Booking module: time-slot booking, extension
- Payment module: online payment and auto-charge
- Navigation module: route to parking + indoor guidance
- Owner cabinet module: tariff setup, utilization stats
- Analytics module: hourly load, revenue, peak forecast, KPI targets

## Tech Stack

- Backend: Python FastAPI
- DB: PostgreSQL, TimescaleDB, Redis
- Queues: MQTT (Mosquitto), RabbitMQ
- Maps: OpenStreetMap + Mapbox API endpoint
- Frontend: React (Vite)

## KPI Targets

- Spot status update: `< 5 sec`
- Booking time: `< 3 sec`
- Scale target: `100000` spots

## Implemented Optional Improvements

- Group A:
  - Forecast of free spots (`predict_free_spots`)
  - Dynamic pricing (`calculate_dynamic_price`)
  - Plate recognition endpoint (`/plates/recognize`)
- Group C:
  - Streaming sensor ingestion (`/sensors/ingest`)
  - Map cache planning (`/maps/cache/plan`)
  - Sharding plan for city districts (`/analytics/sharding/plan`)
  - Async-compatible status workflows via gateway and service APIs
- Group D:
  - Auto-payment by geofence trigger (`/payments/auto-charge`)
  - Telegram booking notification endpoint (`/notify/telegram-booking`)

## Local Run

```bash
cd 'your/project/folder'
docker compose up --build -d
```

## Useful URLs

- Frontend: `http://localhost:5177`
- Gateway health: `http://localhost:8480/health`
- Services health: `http://localhost:8480/services/health`
- Swagger: `http://localhost:8480/docs`

## Validation

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Demo Workflow

```bash
python scripts/demo_pipeline.py
```

## Sample Data Generation

```bash
python scripts/generate_sample_data.py
```

Output file: `data/samples/parking_events.json`

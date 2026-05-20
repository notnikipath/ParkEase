# API Overview

## Gateway

- `GET /health`
- `POST /auth/token`
- `POST /auth/verify`
- `GET /services/health`
- `POST /workflow/find-and-book`
- `POST /workflow/extend-booking`
- `GET /dashboard/{parking_id}`

## Map Service

- `GET /parkings`
- `POST /parkings/search`
- `GET /parkings/{parking_id}`
- `POST /parkings/{parking_id}/free-spots`
- `POST /spots/sync`
- `GET /maps/cache/plan`

## Sensor Service

- `GET /spots`
- `POST /spots/{spot_id}/reserve`
- `POST /spots/{spot_id}/release`
- `POST /spots/{spot_id}/status`
- `POST /sensors/ingest`
- `POST /plates/recognize`
- `GET /processing/plan`

## Booking and Payment

- `POST /bookings`
- `GET /bookings/{booking_id}`
- `POST /bookings/{booking_id}/extend`
- `POST /bookings/{booking_id}/status`
- `POST /payments/charge`
- `POST /payments/auto-charge`
- `GET /payments/by-booking/{booking_id}`

## Navigation

- `POST /routes/build`
- `GET /routes/{route_id}`
- `GET /indoor/{parking_id}/{spot_id}`

## Owner

- `GET /owners/{owner_id}/parkings`
- `POST /owners/{owner_id}/parkings/{parking_id}/tariff`
- `GET /owners/{owner_id}/parkings/{parking_id}/stats`

## Analytics

- `POST /analytics/ingest/booking`
- `POST /analytics/ingest/payment`
- `GET /analytics/load/hourly`
- `GET /analytics/revenue`
- `GET /analytics/forecast`
- `GET /analytics/kpi`
- `GET /analytics/sharding/plan`

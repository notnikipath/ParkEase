# Deployment

## Prerequisites

- Docker Desktop
- Python 3.11+ for local lint/tests

## Start

```bash
cd d:\Шарага\Кинжа10\Task_26_ParkEase
docker compose up --build -d
```

## Stop

```bash
docker compose down
```

## Validate Compose

```bash
docker compose config
```

## Infra Components

- `postgres`
- `timescaledb`
- `redis`
- `rabbitmq`
- `mosquitto`

## Exposed Ports

- Gateway: `8480`
- Frontend: `5177`
- Booking: `8401`
- Navigation: `8402`
- Sensor: `8403`
- Owner: `8404`
- Map: `8405`
- Analytics: `8406`
- Notification: `8407`
- Payment: `8408`

# Optional Improvements Coverage

## Group A

1. Free spot forecasting: implemented in `predict_free_spots`
2. Dynamic pricing: implemented in map and booking logic
3. Plate recognition for auto-entry: `/plates/recognize`
4. EV parking readiness: `supports_ev` and charger-capable spots

## Group B (partial)

1. External navigator integration point: map provider endpoints and route API contract
2. City payment compatibility point: payment abstraction and booking/payment references
3. Tesla API: not directly integrated
4. GIBDD export: not directly integrated

## Group C

1. Stream processing: `/sensors/ingest` + MQTT/RabbitMQ in infra
2. Map caching plan: `/maps/cache/plan`
3. District sharding strategy: `/analytics/sharding/plan`
4. Async status updates: event-style service APIs + workflow orchestration

## Group D (partial)

1. AR indoor hints: `/indoor/{parking_id}/{spot_id}` response includes overlay hint
2. Voice search: not implemented
3. Auto geolocation payment: `/payments/auto-charge`
4. Telegram booking flow: `/notify/telegram-booking`

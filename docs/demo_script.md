# Demo Script

## Goal

Show end-to-end flow: search -> booking -> payment -> reservation -> navigation.

## Steps

1. Start stack:
   - `docker compose up --build -d`
2. Check health:
   - `http://localhost:8480/services/health`
3. Run workflow script:
   - `python scripts/demo_pipeline.py`
4. Open dashboard:
   - `http://localhost:5177`
5. Trigger "Run find-and-book demo" button in UI.
6. Verify analytics KPI:
   - `GET /analytics/kpi`

## Expected Result

- A booking is created and confirmed
- Payment is charged
- Spot status becomes `reserved`
- Navigation route with ETA is returned
- Notification is queued
- KPI metrics are updated

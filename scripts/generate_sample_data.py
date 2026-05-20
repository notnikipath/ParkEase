from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

PARKINGS = ["PARK-CENTER-01", "PARK-STREET-07", "PARK-PRIVATE-11"]
SPOTS = [
    "SPOT-C1-001",
    "SPOT-C1-002",
    "SPOT-C1-003",
    "SPOT-A7-014",
    "SPOT-A7-015",
    "SPOT-P11-006",
]
EVENT_TYPES = ["occupancy", "plate_detected", "entry", "exit"]


def generate_record(index: int) -> dict:
    parking_id = random.choice(PARKINGS)
    spot_id = random.choice(SPOTS)
    event_type = random.choice(EVENT_TYPES)
    occupied = random.choice([True, False])
    return {
        "event_id": f"EV-{index:06d}",
        "parking_id": parking_id,
        "spot_id": spot_id,
        "event_type": event_type,
        "occupied": occupied,
        "plate_number": f"A{random.randint(100,999)}BC77" if event_type == "plate_detected" else None,
        "confidence": round(random.uniform(0.75, 0.99), 2),
        "source": random.choice(["sensor", "camera"]),
        "event_time": (datetime.now(UTC) - timedelta(seconds=index * 2)).isoformat(),
    }


if __name__ == "__main__":
    random.seed(42)
    output = Path(__file__).resolve().parents[1] / "data" / "samples" / "parking_events.json"
    payload = [generate_record(index) for index in range(1, 12001)]
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} records to {output}")

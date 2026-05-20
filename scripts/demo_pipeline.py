from __future__ import annotations

import json
import urllib.request

BASE = "http://localhost:8480"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    result = request(
        "POST",
        "/workflow/find-and-book",
        {
            "user_id": "USR-DEMO",
            "location": {"lat": 55.758, "lon": 37.615},
            "duration_minutes": 90,
            "plate_number": "T900TT77",
            "radius_km": 5,
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

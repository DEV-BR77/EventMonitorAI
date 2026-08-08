import os

import requests

API_URL = os.getenv("EVENTMONITOR_API_URL", "http://127.0.0.1:8000/events")
TELEMETRY_URL = os.getenv(
    "EVENTMONITOR_TELEMETRY_URL",
    API_URL.rstrip("/") + "/telemetry",
)
API_KEY = os.getenv("EVENTMONITOR_API_KEY", "")


def send_event(
    label: str,
    confidence: float,
    db_level: float,
    device: str,
    timestamp: str,
    end_timestamp: str | None = None,
    duration_seconds: float = 0.975,
    avg_db_level: float | None = None,
) -> bool:
    payload = {
        "timestamp": timestamp,
        "end_timestamp": end_timestamp or timestamp,
        "duration_seconds": duration_seconds,
        "event_type": "AUDIO",
        "label": label,
        "confidence": confidence,
        "db_level": db_level,
        "avg_db_level": (avg_db_level if avg_db_level is not None else db_level),
        "device": device,
    }

    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers={"X-API-Key": API_KEY} if API_KEY else None,
            timeout=5,
        )

        response.raise_for_status()

        print(
            f"✓ Ereignis gespeichert: {label} "
            f"| Dauer={duration_seconds:.1f}s "
            f"| Max={db_level:.1f} dB "
            f"| Mittel={payload['avg_db_level']:.1f} dB"
        )

        return True

    except Exception as ex:
        print("API Fehler:", ex)
        return False


def send_telemetry(payload: dict[str, object]) -> bool:
    try:
        response = requests.post(
            TELEMETRY_URL,
            json=payload,
            headers={"X-API-Key": API_KEY} if API_KEY else None,
            timeout=5,
        )
        response.raise_for_status()
        return True
    except Exception as ex:
        print("Telemetrie-API-Fehler:", ex)
        return False

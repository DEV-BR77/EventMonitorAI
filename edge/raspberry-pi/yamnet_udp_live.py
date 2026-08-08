import csv
import os
import socket
from datetime import datetime, timedelta

import numpy as np
from noise_api import send_event
from tflite_runtime.interpreter import Interpreter

UDP_PORT = 12345
SAMPLE_RATE = 16000
WINDOW_SECONDS = 0.975
SAMPLES_PER_WINDOW = int(SAMPLE_RATE * WINDOW_SECONDS)

MODEL_PATH = "/home/admin/yamnet/model/yamnet.tflite"
CLASS_MAP = "/home/admin/yamnet/model/yamnet_class_map.csv"

DEFAULT_DEVICE_NAMES = {
    "192.168.178.193": "ESP32-Quelle-1",
    "192.168.178.190": "ESP32-Quelle-2",
}

SCORE_THRESHOLD = 0.20
MIN_DB_LEVEL = 45.0
CALIBRATION_OFFSET_DB = 100.0

# Ein Ereignis endet nach drei Sekunden ohne relevantes Geräusch.
EVENT_END_SILENCE_SECONDS = 3.0

IGNORED_LABELS = {
    "Silence",
    "Inside, small room",
    "White noise",
}


def load_labels() -> list[str]:
    labels: list[str] = []

    with open(CLASS_MAP, newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            labels.append(row["display_name"])

    return labels


def calc_db(frame: np.ndarray) -> float:
    rms = np.sqrt(np.mean(frame.astype(np.float32) ** 2))

    if rms <= 0:
        return 0.0

    return round(
        20 * np.log10(rms / 32768.0) + CALIBRATION_OFFSET_DB,
        1,
    )


def is_relevant_event(
    label: str,
    confidence: float,
    db_level: float,
) -> bool:
    return (
        confidence >= SCORE_THRESHOLD and label not in IGNORED_LABELS and db_level >= MIN_DB_LEVEL
    )


def start_event(
    frame_start: datetime,
    frame_end: datetime,
    label: str,
    confidence: float,
    db_level: float,
) -> dict:
    print(f"▶ Ereignis gestartet: {label} " f"| {db_level:.1f} dB")

    return {
        "start_time": frame_start,
        "last_relevant_end": frame_end,
        "best_label": label,
        "best_confidence": confidence,
        "max_db_level": db_level,
        "db_sum": db_level,
        "window_count": 1,
    }


def update_event(
    event: dict,
    frame_end: datetime,
    label: str,
    confidence: float,
    db_level: float,
) -> None:
    event["last_relevant_end"] = frame_end
    event["db_sum"] += db_level
    event["window_count"] += 1

    if db_level > event["max_db_level"]:
        event["max_db_level"] = db_level

    if confidence > event["best_confidence"]:
        event["best_label"] = label
        event["best_confidence"] = confidence


def load_device_names() -> dict[str, str]:
    """Load optional `ip=name,ip=name` overrides from the environment."""
    configured = os.getenv("EVENTMONITOR_DEVICES", "").strip()
    if not configured:
        return DEFAULT_DEVICE_NAMES

    devices: dict[str, str] = {}
    for entry in configured.split(","):
        address, separator, name = entry.partition("=")
        if not separator or not address.strip() or not name.strip():
            raise ValueError("EVENTMONITOR_DEVICES must use the format ip=name,ip=name")
        devices[address.strip()] = name.strip()
    return devices


def finish_event(event: dict, device_name: str) -> bool:
    start_time = event["start_time"]
    end_time = event["last_relevant_end"]

    duration_seconds = max(
        (end_time - start_time).total_seconds(),
        WINDOW_SECONDS,
    )

    avg_db_level = event["db_sum"] / event["window_count"]

    print(
        f"■ Ereignis abgeschlossen: "
        f"{event['best_label']} "
        f"| Dauer={duration_seconds:.1f}s "
        f"| Max={event['max_db_level']:.1f} dB "
        f"| Mittel={avg_db_level:.1f} dB"
    )

    return send_event(
        label=event["best_label"],
        confidence=event["best_confidence"],
        db_level=event["max_db_level"],
        avg_db_level=round(avg_db_level, 1),
        device=device_name,
        timestamp=start_time.isoformat(timespec="seconds"),
        end_timestamp=end_time.isoformat(timespec="seconds"),
        duration_seconds=round(duration_seconds, 3),
    )


labels = load_labels()
device_names = load_device_names()

interpreter = Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", UDP_PORT))

print(f"YAMNet UDP aggregation listening on {UDP_PORT}")
print(f"Schwellwert={MIN_DB_LEVEL:.1f} dB " f"| Ende nach {EVENT_END_SILENCE_SECONDS:.1f}s Ruhe")
for source_ip, device_name in device_names.items():
    print(f"Quelle {source_ip} -> {device_name}")

audio_by_source: dict[str, np.ndarray] = {}
active_events: dict[str, dict] = {}

try:
    while True:
        data, address = sock.recvfrom(4096)
        source_ip = address[0]
        device_name = device_names.get(source_ip, f"ESP32-{source_ip}")

        chunk = np.frombuffer(data, dtype=np.int16)
        audio = np.concatenate(
            (audio_by_source.get(source_ip, np.array([], dtype=np.int16)), chunk)
        )

        while len(audio) >= SAMPLES_PER_WINDOW:
            frame = audio[:SAMPLES_PER_WINDOW]
            audio = audio[SAMPLES_PER_WINDOW:]

            frame_end = datetime.now()
            frame_start = frame_end - timedelta(seconds=WINDOW_SECONDS)

            db_level = calc_db(frame)
            waveform = frame.astype(np.float32) / 32768.0

            interpreter.set_tensor(
                input_details[0]["index"],
                waveform,
            )
            interpreter.invoke()

            scores = interpreter.get_tensor(output_details[0]["index"])[0]

            best_idx = int(np.argmax(scores))
            best_label = labels[best_idx]
            best_score = float(scores[best_idx])
            if best_score >= SCORE_THRESHOLD:
                print(
                    f"{frame_end.isoformat(timespec='seconds')} "
                    f"| {device_name:20s} "
                    f"| {best_label:30s} "
                    f"| score={best_score:.3f} "
                    f"| db={db_level:.1f}"
                )

            relevant = is_relevant_event(
                best_label,
                best_score,
                db_level,
            )

            if relevant:
                if source_ip not in active_events:
                    active_events[source_ip] = start_event(
                        frame_start,
                        frame_end,
                        best_label,
                        best_score,
                        db_level,
                    )
                else:
                    update_event(
                        active_events[source_ip],
                        frame_end,
                        best_label,
                        best_score,
                        db_level,
                    )

            elif source_ip in active_events:
                active_event = active_events[source_ip]
                quiet_seconds = (frame_end - active_event["last_relevant_end"]).total_seconds()

                if quiet_seconds >= EVENT_END_SILENCE_SECONDS:
                    if finish_event(active_event, device_name):
                        del active_events[source_ip]

        audio_by_source[source_ip] = audio

except KeyboardInterrupt:
    print("\nYAMNet wird beendet.")

    for source_ip, active_event in active_events.items():
        device_name = device_names.get(source_ip, f"ESP32-{source_ip}")
        finish_event(active_event, device_name)

finally:
    sock.close()

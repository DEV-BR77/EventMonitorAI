import csv
import multiprocessing as mp
import os
import queue
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from time import monotonic

import numpy as np
from audio_protocol import decode_packet, sequence_gap
from noise_api import send_event, send_telemetry
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
TELEMETRY_INTERVAL_SECONDS = 5.0

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

# The first TFLite invocation initializes optimized kernels. Warm them up before
# opening the UDP socket so that startup work cannot delay packet reception.
interpreter.set_tensor(
    input_details[0]["index"],
    np.zeros(SAMPLES_PER_WINDOW, dtype=np.float32),
)
interpreter.invoke()


def receive_packets(packet_queue: mp.Queue, receiver_stop: mp.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.settimeout(1.0)
    sock.bind(("0.0.0.0", UDP_PORT))
    while not receiver_stop.is_set():
        try:
            packet = sock.recvfrom(4096)
            packet_queue.put(packet, timeout=0.5)
        except TimeoutError:
            continue
        except (OSError, queue.Full):
            if not receiver_stop.is_set():
                print("UDP-Empfangspuffer ist ausgelastet.")
    sock.close()


process_context = mp.get_context("fork")
packet_queue = process_context.Queue(maxsize=4096)
receiver_stop = process_context.Event()
receiver_process = process_context.Process(
    target=receive_packets,
    args=(packet_queue, receiver_stop),
    name="eventmonitor-udp",
    daemon=True,
)
receiver_process.start()

print(f"YAMNet UDP aggregation listening on {UDP_PORT}")
print(f"Schwellwert={MIN_DB_LEVEL:.1f} dB " f"| Ende nach {EVENT_END_SILENCE_SECONDS:.1f}s Ruhe")
for source_ip, device_name in device_names.items():
    print(f"Quelle {source_ip} -> {device_name}")

audio_by_source: dict[str, np.ndarray] = {}
active_events: dict[str, dict] = {}
transport_by_source: dict[str, dict] = {}
api_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="eventmonitor-api")

try:
    while True:
        data, address = packet_queue.get()
        source_ip = address[0]
        try:
            metadata, pcm_payload = decode_packet(data)
        except ValueError as error:
            print(f"Ungültiges Audiopaket von {source_ip}: {error}")
            continue

        source_key = metadata.device_id if metadata else source_ip
        device_name = device_names.get(
            source_key,
            device_names.get(source_ip, f"ESP32-{source_key}"),
        )
        state = transport_by_source.setdefault(
            source_key,
            {
                "received": 0,
                "lost": 0,
                "last_sequence": None,
                "last_uptime_ms": None,
                "last_telemetry": monotonic(),
                "db_level": 0.0,
            },
        )
        state["received"] += 1
        if metadata:
            rebooted = (
                state["last_uptime_ms"] is not None and metadata.uptime_ms < state["last_uptime_ms"]
            )
            if rebooted:
                print(f"Neustart erkannt: {device_name}")
                state["received"] = 1
                state["lost"] = 0
                state["last_sequence"] = None
            lost = sequence_gap(state["last_sequence"], metadata.sequence)
            state["lost"] += lost
            state["last_sequence"] = metadata.sequence
            state["last_uptime_ms"] = metadata.uptime_ms
            if lost:
                print(
                    f"Paketverlust {device_name}: {lost} Paket(e) "
                    f"vor Sequenz {metadata.sequence}"
                )

            now_monotonic = monotonic()
            if now_monotonic - state["last_telemetry"] >= TELEMETRY_INTERVAL_SECONDS:
                state["last_telemetry"] = now_monotonic
                api_executor.submit(
                    send_telemetry,
                    {
                        "device_id": source_key,
                        "source_ip": source_ip,
                        "protocol_version": metadata.protocol_version,
                        "firmware_version": metadata.firmware_version,
                        "sample_rate": metadata.sample_rate,
                        "uptime_ms": metadata.uptime_ms,
                        "packets_received": state["received"],
                        "packets_lost": state["lost"],
                        "peak": metadata.peak,
                        "db_level": state["db_level"],
                    },
                )

        chunk = np.frombuffer(pcm_payload, dtype=np.int16)
        audio = np.concatenate(
            (audio_by_source.get(source_key, np.array([], dtype=np.int16)), chunk)
        )

        while len(audio) >= SAMPLES_PER_WINDOW:
            frame = audio[:SAMPLES_PER_WINDOW]
            audio = audio[SAMPLES_PER_WINDOW:]

            frame_end = datetime.now()
            frame_start = frame_end - timedelta(seconds=WINDOW_SECONDS)

            db_level = calc_db(frame)
            state["db_level"] = db_level
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
                if source_key not in active_events:
                    active_events[source_key] = start_event(
                        frame_start,
                        frame_end,
                        best_label,
                        best_score,
                        db_level,
                    )
                else:
                    update_event(
                        active_events[source_key],
                        frame_end,
                        best_label,
                        best_score,
                        db_level,
                    )

            elif source_key in active_events:
                active_event = active_events[source_key]
                quiet_seconds = (frame_end - active_event["last_relevant_end"]).total_seconds()

                retry_after = active_event.get("delivery_retry_after", 0.0)
                if quiet_seconds >= EVENT_END_SILENCE_SECONDS and monotonic() >= retry_after:
                    if finish_event(active_event, device_name):
                        del active_events[source_key]
                    else:
                        active_event["delivery_retry_after"] = monotonic() + 30.0

        audio_by_source[source_key] = audio

except KeyboardInterrupt:
    print("\nYAMNet wird beendet.")

    for source_ip, active_event in active_events.items():
        device_name = device_names.get(source_ip, f"ESP32-{source_ip}")
        finish_event(active_event, device_name)

finally:
    receiver_stop.set()
    receiver_process.join(timeout=2)
    if receiver_process.is_alive():
        receiver_process.terminate()
    api_executor.shutdown(wait=False, cancel_futures=True)

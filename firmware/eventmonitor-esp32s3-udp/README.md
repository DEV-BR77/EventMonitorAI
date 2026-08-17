# ESP32-S3 UDP audio firmware

Reference hardware: Freenove ESP32-S3 WROOM N16R8 with 16 MB flash, 8 MB PSRAM
and an INMP441 microphone.

Each UDP datagram contains a versioned EventMonitorAI header with a stable
device ID, sequence number, firmware version and transport telemetry. The
Raspberry Pi can therefore detect packet loss and report device health.

## Wiring

| INMP441 | ESP32-S3 |
|---|---|
| SCK/BCLK | GPIO 5 |
| WS/LRCL | GPIO 4 |
| SD | GPIO 6 |
| VDD | 3.3 V |
| GND | GND |
| L/R | GND (left channel) |

## Local setup on Windows

PlatformIO is kept in a firmware-specific virtual environment so that its Python
dependencies cannot interfere with the FastAPI backend.

```powershell
cd firmware\eventmonitor-esp32s3-udp
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install platformio
Copy-Item include\secrets.example.h include\secrets.h
```

Enter the local WLAN credentials in `include/secrets.h`. This file is ignored by Git.
Set `UDP_TARGET_IP` in `src/main.cpp` to the Raspberry Pi address.
Generate the shared clip-upload token and optionally provision it on the Pi without
printing the secret:

```powershell
python ..\..\scripts\provision_clip_token.py --ssh-target admin@192.168.178.194
```

## Build and flash

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m platformio device list
.\.venv\Scripts\python.exe -m platformio run
.\.venv\Scripts\python.exe -m platformio run --target upload --upload-port COM3
```

Replace `COM3` if `device list` reports another port. The project no longer hard-codes
a workstation-specific serial port.

The firmware streams signed 16-bit mono PCM at 16 kHz via UDP port 12345. It targets
`192.168.178.194` and reports status every two seconds on the UART serial output at
115200 baud.

Existing devices that still target the former address `192.168.178.64` remain
compatible through a persistent secondary address on the receiver. New firmware
must use the canonical receiver address `.194`.

## PSRAM event clips

The N16R8 PSRAM holds a continuously rotating two-second PCM ring buffer. Once a
packet peak reaches `EVENT_TRIGGER_PEAK`, the firmware snapshots the complete
pre-trigger buffer, appends three seconds after the trigger and creates a five-second
WAV clip (80,000 samples, 160,044 bytes). Triggering starts only after the ring is
fully populated and has a ten-second cooldown.

Clip upload runs in a separate FreeRTOS task, so the UDP live stream continues while
the board sends the WAV to the Pi on TCP port 12346. The upload uses the same stable
device ID as UDP, a shared secret header and up to three delivery attempts. The Pi
validates authentication, size, WAV format, channel count, bit depth, sample rate and
duration before atomically storing the clip and its SHA-256 metadata sidecar.

# ESP32-S3 UDP audio firmware

Reference hardware: Freenove ESP32-S3 WROOM N16R8 with 16 MB flash, 8 MB PSRAM
and an INMP441 microphone.

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

The firmware streams signed 16-bit mono PCM at 16 kHz via UDP port 12345. It currently
targets `192.168.178.64` and reports status every two seconds on the UART serial output
at 115200 baud.

# Hardware

## Current reference setup

- ESP32-S3 with PSRAM
- INMP441 digital I2S microphone
- Raspberry Pi as UDP receiver and edge classifier
- Optional Windows or Linux server for backend and AudioLab

Pin assignments, enclosure design, microphone calibration and supported alternatives will be documented as the hardware prototype stabilizes.

Never commit `secrets.h`. Copy `secrets.example.h` to `secrets.h` and enter local credentials only on the development machine.

The Freenove ESP32-S3 N16R8 uses 224,000 bytes of its 8 MB PSRAM for event capture:
64,000 bytes for the two-second pre-trigger ring and 160,000 bytes for the complete
five-second event clip. If PSRAM initialization fails, live UDP audio remains active
but event clips are disabled and the condition is reported on the serial console.

# Hardware

## Current reference setup

- ESP32-S3 with PSRAM
- INMP441 digital I2S microphone
- Raspberry Pi as UDP receiver and edge classifier
- Optional Windows or Linux server for backend and AudioLab

Pin assignments, enclosure design, microphone calibration and supported alternatives will be documented as the hardware prototype stabilizes.

Never commit `secrets.h`. Copy `secrets.example.h` to `secrets.h` and enter local credentials only on the development machine.

# Rev-A preliminary BOM

| References | Part / value | Package | Role |
| --- | --- | --- | --- |
| U1 | ESP32-S3-WROOM-1U-N16R8 | module | MCU and external U.FL antenna connector |
| U2 | CP2102N-A02-GQFN24R (`C969151`) | QFN-24-EP 4×4 mm | USB-to-UART programming bridge; includes DTR and RTS for standard auto-programming |
| U3 | AMS1117-3.3 | SOT-223-3 | 5 V to 3.3 V regulator |
| U4 | USBLC6-2SC6 | SOT-23-6 | USB ESD protection |
| U5 | ICS-43434 | LGA-6 | bottom-port I²S microphone |
| J1 | USB-C USB2.0 receptacle | 16-pin SMD | power and data |
| SW1 / SW2 | SMD tactile switch | 3×4 mm | BOOT / RESET |
| Q1 / Q2 | BC847B | SOT-23 | auto-programming pair |
| D1 | green LED | 0603 | status output |
| R1 / R2 | 5.1 kΩ 1% | 0603 | USB-C CC pull-downs |
| R3 / R4 | 10 kΩ 1% | 0603 | EN and GPIO0 pull-ups |
| R5 | 1 kΩ | 0603 | LED resistor |
| R6 / R7 | 22 Ω | 0603 | optional USB damping |
| R8 / R9 | 499 Ω | 0603 | UART series resistors |
| R10 | 1 kΩ | 0603 | CP2102N reset pull-up |
| C1 | 10 µF 10 V X5R | 0805 | AMS1117 input |
| C2 | 10 µF 6.3 V X5R | 0805 | AMS1117 output |
| C3 / C4 | 100 nF X7R | 0603 | regulator / MCU bypass |
| C5 | 100 nF X7R | 0603 | EN reset capacitor |
| C6 | 1 µF X7R | 0603 | microphone bypass |
| C7 | 100 nF X7R | 0603 | microphone bypass |
| C8 | 4.7 µF 6.3 V X5R | 0805 | CP2102N VDD/VIO bypass |
| C9 | 100 nF X7R | 0603 | CP2102N local bypass |
| H1–H4 | M2.5, 2.7 mm NPTH | PCB | enclosure mounting |
| P1 | U.FL-to-RP-SMA bulkhead pigtail | cable | user supplied; attaches directly to U1 |

Confirmed at the design check: U1 is LCSC `C3013946`, U2 is `C969151`, and U5
is `C5656610`. Every remaining row still requires a currently available
LCSC/JLC part number and footprint check before the PCBA BOM is exported. The
machine-readable draft is kept locally as `BOM_DRAFT.csv`; generated fabrication
BOM/CPL archives remain untracked until the design has passed review.

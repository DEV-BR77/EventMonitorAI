# Rev-A connection map

This document is the reviewed electrical source of truth used to enter the
KiCad schematic. Signal names deliberately match the firmware where applicable.

## USB and power

| Net | Connections |
| --- | --- |
| USB_5V | J1 A4/A9/B4/B9; U3 VIN; C1 positive |
| GND | J1 A1/A12/B1/B12 and shield; U1 all GND + EPAD; U2 GND; U3 GND; U4 GND; U5 GND; all capacitors negative |
| USB_CC1 | J1 A5 → R1 5.1 kΩ → GND |
| USB_CC2 | J1 B5 → R2 5.1 kΩ → GND |
| USB_D+ | J1 A6+B6 → U4 → optional R6 22 Ω → U2 D+ |
| USB_D- | J1 A7+B7 → U4 → optional R7 22 Ω → U2 D- |
| +3V3 | U3 VOUT; U1 3V3; U2 VDD; U5 VDD; C2/C3/C4/C6/C7 positive; pull-ups |

The USB shield joins GND near J1 with a controlled short connection. The final
layout may use a 0 Ω link / EMI option only if pre-compliance testing shows it
is needed; it is not an arbitrary split ground.

## Programming and reset

| Net | Connections |
| --- | --- |
| UART_TX_ESP | U1 pin 37 (U0TXD/GPIO43) → R8 499 Ω → U2 RXD |
| UART_RX_ESP | U1 pin 36 (U0RXD/GPIO44) ← R9 499 Ω ← U2 TXD |
| EN | U1 pin 3; R3 10 kΩ to +3V3; C5 100 nF to GND; SW2 to GND; Q1 auto-reset collector |
| BOOT | U1 pin 27 (GPIO0); R4 10 kΩ to +3V3; SW1 to GND; Q2 auto-boot collector |
| DTR / RTS | U2 control outputs → Espressif two-NPN auto-program circuit Q1/Q2; circuit must reproduce the Espressif truth table so opening a serial port cannot hold EN and GPIO0 low simultaneously |

## Microphone

| Net | Connections |
| --- | --- |
| I2S_WS | U1 pin 4 (GPIO4) → U5 WS |
| I2S_BCLK | U1 pin 5 (GPIO5) → U5 SCK |
| I2S_DATA | U5 SD → U1 pin 6 (GPIO6) |
| MIC_LR | U5 L/R → GND (left-channel selection) |

U5 is a bottom-port microphone: its acoustic port and the matching PCB and
enclosure opening are kept clear. I2S traces are short, contiguous over the
ground plane, and kept apart from USB and the AMS1117 thermal zone.

## Status LED

`GPIO48` → R5 1 kΩ → D1 anode, D1 cathode → GND. Firmware must define the
selected GPIO48 LED polarity before enabling this output.

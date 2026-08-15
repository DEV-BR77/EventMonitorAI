# EventMonitor Audio Node – Rev A, 4 Layer

Status: Engineering baseline. This is the binding starting point for the
schematic and layout; it is not a manufacturing release.

## Architecture

* Module: **ESP32-S3-WROOM-1U-N16R8**. Its own U.FL connector accepts a
  user-supplied U.FL-to-RP-SMA bulkhead pigtail; no RF trace or second U.FL
  connector is put on the PCB.
* USB-C receptacle in USB 2.0 device mode, 5 V input only, with separate 5.1 kΩ
  pull-down resistors from CC1 and CC2 to GND.
* USBLC6-2SC6 (or electrically equivalent, validated JLC basic/extended part)
  directly behind the receptacle. USB D+/D- are routed as a 90-ohm differential
  pair to a CP2102N USB-UART bridge.
* CP2102N connects to U0RXD/GPIO44 and U0TXD/GPIO43. DTR/RTS drive the standard
  two-transistor auto-program circuit for EN and GPIO0. Manual BOOT and RESET
  buttons remain available.
* USB 5 V feeds an AMS1117-3.3. The regulator has 10 µF MLCC at VIN and VOUT,
  a 100 nF VOUT bypass capacitor and a stitched, top-layer VOUT thermal area.
  A first-article thermal test at continuous Wi-Fi transmission is mandatory.
* ICS-43434 is the directly assembled bottom-port I²S microphone. Its data,
  word-select and clock nets use existing firmware pins GPIO6, GPIO4 and GPIO5.
  It gets local 100 nF plus 1 µF decoupling and a dedicated acoustic aperture.

## Stackup and placement rules

The project is a standard **4-layer, 1.6 mm FR-4** design:

| Layer | Intended use |
| --- | --- |
| F.Cu | components, local power and short signals |
| In1.Cu | uninterrupted GND plane |
| In2.Cu | 3V3 plane / low-speed power distribution |
| B.Cu | low-speed routing, microphone region only where unavoidable |

The module shield and exposed pad are stitched to GND. The microphone bottom
port has a keepout and matching opening in the enclosure. USB and CP2102N stay
at the opposite side of the board from the microphone. No copper or mechanical
part may press against or kink the U.FL pigtail.

## Required sign-off before fabrication

1. Select available LCSC part numbers and validate each package against its
   datasheet.
2. Create and review the KiCad schematic; run ERC.
3. Route from that netlist using the selected JLC 4-layer impedance stackup;
   run DRC with zero errors.
4. Check USB-C polarity, auto-program timing and I²S clock/data orientation.
5. Assemble one first article, flash it through USB, run Wi-Fi thermal testing,
   microphone noise-floor testing and antenna range testing.

The current firmware uses BCLK GPIO5, WS GPIO4 and microphone data GPIO6.
UART0 uses GPIO43 (TXD0) and GPIO44 (RXD0), as documented by Espressif.

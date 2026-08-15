# Rev-A Layout Status

Updated: 15 August 2026

## What is in the native KiCad source

`generate_layout.py` generates a 65 x 50 mm, four-layer native KiCad board
with real footprints for the USB-C receptacle, CP2102N-A02-GQFN24R,
ESP32-S3-WROOM-1U-N16R8, AMS1117-3.3, ICS-43434, ESD protection, automatic
boot/reset circuit, controls, LED and four M2.5 mounting holes.

The USB data pair is deliberately split into connector-side and protected-side
nets. It is connected as follows:

`USB-C D+/- -> USBLC6-2SC6 input -> USBLC6-2SC6 output -> 22 ohm series
option -> CP2102N D+/-`.

The USBLC6-2SC6's VBUS pin is tied to USB 5 V and its ground pin is tied to
the ground plane. This follows the device's two pass-through I/O channels;
the final routed board must keep these paths short and symmetric.

## Verified placement gate

The generated board has no component courtyard overlaps. The USB-C footprint
was moved inside the board edge and the power, EN and auto-program components
were spaced apart before routing starts.

The current design-rule report intentionally remains non-zero because this is
still the placement/net-assignment phase:

- The project design rule is explicitly set to a 0.20 mm plated through-hole,
  matching the thermal-ground drills embedded in KiCad's ESP32-S3-WROOM-1U
  footprint and JLCPCB's published recommended 4-layer capability.
- Isolated inner-3V3 copper and silkscreen warnings are expected until the
  final routing, copper pours, reference cleanup and keepouts are complete.
- All 85 electrical connections are still unrouted. Gerber, BOM and CPL
  export are therefore blocked.

## Release gate

This source is **not order-ready**. The next required steps are: route USB as
a controlled 90-ohm differential pair, route power and remaining signals,
add antenna/microphone copper keepouts and stitching vias, set the board
manufacturer constraints, run a clean DRC, then export and visually inspect
Gerber, BOM and CPL. Only that clean export may be uploaded to JLCPCB.

# Rev-A layout status

Updated: 16 August 2026

## Native KiCad source

`eventmonitor_audio_node_rev_a.kicad_pcb` is the native, version-controlled
65 x 50 mm four-layer board. `generate_layout.py` recreates the reviewed
placement, copper planes and routing for the USB-C receptacle,
USBLC6-2SC6 ESD protection, CP2102N-A02-GQFN24R programming bridge,
ESP32-S3-WROOM-1U-N16R8, AMS1117-3.3, ICS-43434 microphone, automatic
boot/reset circuit, buttons, status LED and four M2.5 mounting holes.

## Completed routing gate

The complete board now passes KiCad's native DRC:

- **0 DRC violations**
- **0 unconnected pads**
- **0 footprint errors**

The rebuilt USB/programming area contains:

- separate 5.1 kOhm CC1/CC2 pull-down paths;
- connector-side D+/D- into USBLC6-2SC6 before downstream circuitry;
- protected D+/D- through 22 ohm series resistors to CP2102N;
- protected-side USB tracks balanced to 6.875 mm (D+) and 7.297 mm (D-);
- a dedicated, wider USB 5 V trunk to the ESD array, CP2102N supply,
  AMS1117 input and 10 uF input capacitor;
- CP2102N UART, DTR/RTS auto-programming, EN, BOOT and RESET routing;
- direct ground returns for the ESD array, USB shield and microphone.

USB-C power exits toward the board edge before changing layers. The routing
therefore avoids the connector shield holes, and no unfilled via is placed
inside a USB-C SMD contact pad. Fine USB/QFN transitions use 0.40/0.20 mm vias;
routed supply transitions use 0.60/0.30 mm vias.

## Fabrication release gate

The clean DRC makes this a routed engineering board, but it is **not yet an
unconditional production release**. Before ordering assembled boards:

1. create/review the matching KiCad schematic and pass ERC;
2. select the actual JLCPCB four-layer stackup, calculate the 90-ohm USB
   width/spacing for that stackup and re-run DRC after any tuning;
3. add and mechanically verify the microphone acoustic opening/keepout against
   the enclosure;
4. assign and stock-check every remaining LCSC part number and verify each
   footprint against the manufacturer's datasheet;
5. export and visually inspect Gerber/drill, BOM and CPL, then perform a
   first-article USB programming, Wi-Fi thermal, microphone noise-floor and
   antenna range test.

Generated DRC reports, renders and fabrication outputs remain untracked and
must not be committed as source or mistaken for an approved production release.

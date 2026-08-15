# Rev-A placement plan

Board size: **65 × 50 mm**, 1.6 mm, four layers, with four M2.5 mounting holes.

| Area | Placement | Reason |
| --- | --- | --- |
| Left edge | USB-C J1 | Accessible from the enclosure; shortest protected USB path. |
| Left / upper | USBLC6 U4 then CP2102N U2 | ESD sits first, USB pair stays short and isolated from audio. |
| Left / lower | AMS1117 U3, input/output capacitors | Short 5 V path and copper thermal area on top plus thermal vias. |
| Centre / upper | ESP32-S3-WROOM-1U U1 | Clear path for the U.FL pigtail toward the enclosure wall. |
| Right / lower | ICS-43434 U5 and C6/C7 | Largest possible distance from USB and regulator; aligned with enclosure acoustic opening. |
| Bottom / centre | BOOT and RESET | Reachable from outside without affecting USB or microphone. |
| Upper / centre | Status LED D1 | Visible through a small light pipe/window. |

The board uses a full In1 GND plane. In2 contains +3V3 plus only short local
power islands. The microphone's port has an unmasked keepout on every copper
layer and must line up with an enclosure hole. The WROOM-1U carries its own
U.FL connector; the pigtail runs directly from the module to the RP-SMA
bulkhead, with no RF trace on this board.

This placement is the input for the KiCad layout. Mechanical dimensions of the
eventual enclosure may still move USB, button and microphone coordinates, but
not their electrical ordering.

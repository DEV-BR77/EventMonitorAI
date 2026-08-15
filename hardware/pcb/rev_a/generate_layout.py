"""Create the KiCad Rev-A placement board from the reviewed placement plan.

This script deliberately stops after footprint placement and board stackup.  It
is the controlled starting point for routing; fabrication export is forbidden
until the schematic-net import and DRC zero-error gate are complete.
"""
from __future__ import annotations

from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
OUT = HERE / "generated"
FOOTPRINTS = Path(r"E:\Apps\KiCad\share\kicad\footprints")


def mm(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def load(board: pcbnew.BOARD, lib: str, footprint: str, ref: str, value: str,
         x: float, y: float, rotation: float = 0) -> None:
    item = pcbnew.FootprintLoad(str(FOOTPRINTS / f"{lib}.pretty"), footprint)
    if item is None:
        raise RuntimeError(f"missing footprint {lib}:{footprint}")
    item.SetReference(ref)
    item.SetValue(value)
    item.SetPosition(mm(x, y))
    item.SetOrientationDegrees(rotation)
    board.Add(item)


def edge(board: pcbnew.BOARD, width: float, height: float) -> None:
    for (x1, y1), (x2, y2) in zip(
        ((0, 0), (width, 0), (width, height), (0, height)),
        ((width, 0), (width, height), (0, height), (0, 0)),
    ):
        line = pcbnew.PCB_SHAPE(board)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(mm(x1, y1))
        line.SetEnd(mm(x2, y2))
        line.SetLayer(pcbnew.Edge_Cuts)
        line.SetWidth(pcbnew.FromMM(0.2))
        board.Add(line)


def text(board: pcbnew.BOARD, value: str, x: float, y: float, size: float = 1.2) -> None:
    label = pcbnew.PCB_TEXT(board)
    label.SetText(value)
    label.SetPosition(mm(x, y))
    label.SetLayer(pcbnew.F_SilkS)
    label.SetTextSize(mm(size, size))
    label.SetTextThickness(pcbnew.FromMM(0.2))
    board.Add(label)


def copper_plane(board: pcbnew.BOARD, signal: pcbnew.NETINFO_ITEM, layer: int,
                 inset: float = 0.5) -> None:
    """Add a board-wide plane. Fine keepouts are added during final routing."""
    area = pcbnew.ZONE(board)
    area.SetNet(signal)
    area.SetLayer(layer)
    area.SetLocalClearance(pcbnew.FromMM(0.2))
    area.SetMinThickness(pcbnew.FromMM(0.2))
    polygon = area.Outline()
    polygon.NewOutline()
    for point in ((inset, inset), (65 - inset, inset), (65 - inset, 50 - inset),
                  (inset, 50 - inset)):
        polygon.Append(mm(*point))
    board.Add(area)


def route(board: pcbnew.BOARD, signal: pcbnew.NETINFO_ITEM,
          points: tuple[tuple[float, float], ...], width: float = 0.25,
          layer: int = pcbnew.F_Cu) -> None:
    """Add one intentionally reviewed polyline, never an autorouted guess."""
    for start, end in zip(points, points[1:]):
        item = pcbnew.PCB_TRACK(board)
        item.SetStart(mm(*start))
        item.SetEnd(mm(*end))
        item.SetWidth(pcbnew.FromMM(width))
        item.SetLayer(layer)
        item.SetNet(signal)
        board.Add(item)


def power_via(board: pcbnew.BOARD, signal: pcbnew.NETINFO_ITEM,
              x: float, y: float) -> None:
    """0.60/0.30 mm F.Cu-to-In2.Cu power-plane transition."""
    item = pcbnew.PCB_VIA(board)
    item.SetPosition(mm(x, y))
    item.SetWidth(pcbnew.FromMM(0.60))
    item.SetDrill(pcbnew.FromMM(0.30))
    item.SetLayerPair(pcbnew.F_Cu, pcbnew.In2_Cu)
    item.SetNet(signal)
    board.Add(item)


def signal_via(board: pcbnew.BOARD, signal: pcbnew.NETINFO_ITEM,
               x: float, y: float) -> None:
    """0.50/0.25 mm F.Cu-to-B.Cu transition for a low-speed signal."""
    item = pcbnew.PCB_VIA(board)
    item.SetPosition(mm(x, y))
    item.SetWidth(pcbnew.FromMM(0.50))
    item.SetDrill(pcbnew.FromMM(0.25))
    item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    item.SetNet(signal)
    board.Add(item)


def make() -> Path:
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    # JLCPCB's published 4-layer capability recommends a 0.20 mm PTH drill.
    # The ESP32 module footprint uses 0.20 mm thermal-ground drills.
    board.GetDesignSettings().m_MinThroughDrill = pcbnew.FromMM(0.20)
    edge(board, 65, 50)
    nets = {}
    for name in ("GND", "+3V3", "USB_5V", "USB_D+", "USB_D-", "USB_D+_ESD", "USB_D-_ESD", "USB_CC1", "USB_CC2",
                 "UART_TX_ESP", "UART_RX_ESP", "UART_RX_CP", "UART_TX_CP", "EN", "BOOT",
                 "I2S_WS", "I2S_BCLK", "I2S_DATA", "U2_RST", "AUTO_DTR", "AUTO_RTS",
                 "Q1_BASE", "Q2_BASE", "LED_STATUS", "LED_A"):
        item = pcbnew.NETINFO_ITEM(board, name)
        board.Add(item)
        nets[name] = item
    # x/y are deliberate Rev-A locations, not arbitrary quote coordinates.
    parts = (
        # Keep the physical connector pads well inside the board outline.
        ("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J1", "USB-C USB2.0", 5.7, 25, 90),
        ("Package_TO_SOT_SMD", "SOT-23-6", "U4", "USBLC6-2SC6", 12.5, 19, 0),
        ("Package_DFN_QFN", "QFN-24-1EP_4x4mm_P0.5mm_EP2.65x2.65mm", "U2", "CP2102N-A02-GQFN24R", 20, 20, 0),
        ("Package_TO_SOT_SMD", "SOT-223-3_TabPin2", "U3", "AMS1117-3.3", 18, 38, 0),
        ("RF_Module", "ESP32-S3-WROOM-1U", "U1", "ESP32-S3-WROOM-1U-N16R8", 45, 23, 90),
        ("Sensor_Audio", "InvenSense_ICS-43434-6_3.5x2.65mm", "U5", "ICS-43434", 55, 41, 0),
        ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A", "SW1", "BOOT", 34, 43, 0),
        ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A", "SW2", "RESET", 43, 43, 0),
        ("LED_SMD", "LED_0603_1608Metric", "D1", "GREEN", 34, 6, 0),
    )
    for part in parts:
        load(board, *part)
    # Passive placements: power at lower left, USB at upper left, microphone
    # decoupling next to U5, and boot/reset support above their buttons.
    passive = (
        ("R1", "5.1k", 9, 11), ("R2", "5.1k", 9, 14),
        ("R3", "10k EN", 30, 35), ("R4", "10k BOOT", 37, 35),
        ("R5", "1k LED", 34, 10), ("R6", "22R D+", 14, 22),
        ("R7", "22R D-", 14, 25), ("R8", "499R TX", 27, 18),
        ("R9", "499R RX", 27, 21), ("R10", "1k U2 RST", 25, 14),
        ("R11", "10k DTR", 21, 31), ("R12", "10k RTS", 29, 31),
    )
    for ref, value, x, y in passive:
        load(board, "Resistor_SMD", "R_0603_1608Metric", ref, value, x, y)
    caps = (
        ("C1", "10u VIN", 10, 34), ("C2", "10u VOUT", 25, 38),
        ("C3", "100n U3", 26, 34), ("C4", "100n U1", 33, 12),
        ("C5", "100n EN", 30, 38), ("C6", "1u MIC", 51, 41),
        ("C7", "100n MIC", 51, 44), ("C8", "4u7 U2", 20, 14),
        ("C9", "100n U2", 24, 10), ("C10", "1u EN", 34, 38),
    )
    for ref, value, x, y in caps:
        load(board, "Capacitor_SMD", "C_0805_2012Metric" if ref in {"C1", "C2", "C8"} else "C_0603_1608Metric", ref, value, x, y)
    for ref, x, y in (("Q1", 26, 27), ("Q2", 31, 27)):
        load(board, "Package_TO_SOT_SMD", "SOT-23", ref, "BC847B", x, y)
    for ref, x, y in (("H1", 4, 4), ("H2", 61, 4), ("H3", 4, 46), ("H4", 61, 46)):
        load(board, "MountingHole", "MountingHole_2.7mm_M2.5_DIN965_Pad", ref, "M2.5", x, y)

    def connect(ref: str, pad: str, name: str) -> None:
        footprint = board.FindFootprintByReference(ref)
        selected = footprint.FindPadByNumber(pad)
        if selected is None:
            raise RuntimeError(f"missing pad {ref}.{pad}")
        selected.SetNet(nets[name])

    def connect_all(ref: str, pad: str, name: str) -> None:
        footprint = board.FindFootprintByReference(ref)
        matched = [item for item in footprint.Pads() if item.GetNumber() == pad]
        if not matched:
            raise RuntimeError(f"missing pad {ref}.{pad}")
        for selected in matched:
            selected.SetNet(nets[name])

    # USB-C receptacle and ESD array (USBLC6-2SC6 pin pairs 1/6 and 3/4).
    for pad in ("A1", "A12", "B1", "B12"):
        connect("J1", pad, "GND")
    connect_all("J1", "SH", "GND")
    for pad in ("A4", "A9", "B4", "B9"):
        connect("J1", pad, "USB_5V")
    for pad, name in (("A5", "USB_CC1"), ("B5", "USB_CC2"), ("A6", "USB_D+_ESD"),
                      ("B6", "USB_D+_ESD"), ("A7", "USB_D-_ESD"), ("B7", "USB_D-_ESD")):
        connect("J1", pad, name)
    for pad, name in (("1", "USB_D+_ESD"), ("6", "USB_D+_ESD"), ("3", "USB_D-_ESD"),
                      ("4", "USB_D-_ESD"), ("2", "GND"), ("5", "USB_5V")):
        connect("U4", pad, name)

    # CP2102N-A02-GQFN24R; VIO/VDD/VREGIN use the external 3V3 rail.
    for pad in ("2", "25"):
        connect("U2", pad, "GND")
    for pad in ("5", "6", "7"):
        connect("U2", pad, "+3V3")
    for pad, name in (("3", "USB_D+"), ("4", "USB_D-"), ("8", "USB_5V"),
                      ("9", "U2_RST"), ("19", "AUTO_RTS"), ("20", "UART_RX_CP"),
                      ("21", "UART_TX_CP"), ("23", "AUTO_DTR")):
        connect("U2", pad, name)

    # ESP32-S3-WROOM-1U pins from the Espressif WROOM-1U pin table.
    for pad in ("1", "40"):
        connect("U1", pad, "GND")
    connect_all("U1", "41", "GND")
    for pad, name in (("2", "+3V3"), ("3", "EN"), ("4", "I2S_WS"),
                      ("5", "I2S_BCLK"), ("6", "I2S_DATA"), ("27", "BOOT"),
                      ("36", "UART_RX_ESP"), ("37", "UART_TX_ESP"), ("25", "LED_STATUS")):
        connect("U1", pad, name)

    # ICS-43434: SD, VDD, GND, SCK, WS, L/R. L/R low selects the left channel.
    for pad, name in (("1", "I2S_DATA"), ("2", "+3V3"), ("3", "GND"),
                      ("4", "I2S_BCLK"), ("5", "I2S_WS"), ("6", "GND")):
        connect("U5", pad, name)
    connect("U3", "1", "USB_5V")
    connect_all("U3", "2", "+3V3")
    connect("U3", "3", "GND")

    # Passive network assignments.
    for ref, net in (("R1", "USB_CC1"), ("R2", "USB_CC2"), ("R3", "EN"),
                     ("R4", "BOOT"), ("R5", "LED_STATUS"), ("R6", "USB_D+_ESD"),
                     ("R7", "USB_D-_ESD"), ("R8", "UART_TX_ESP"),
                     ("R9", "UART_RX_ESP"), ("R10", "U2_RST"), ("R11", "AUTO_DTR"),
                     ("R12", "AUTO_RTS")):
        connect(ref, "1", net)
    for ref, net in (("R1", "GND"), ("R2", "GND"), ("R3", "+3V3"),
                     ("R4", "+3V3"), ("R5", "LED_A"), ("R6", "USB_D+"),
                     ("R7", "USB_D-"), ("R8", "UART_RX_CP"),
                     ("R9", "UART_TX_CP"), ("R10", "+3V3"), ("R11", "Q1_BASE"),
                     ("R12", "Q2_BASE")):
        connect(ref, "2", net)
    for ref, left, right in (("C1", "USB_5V", "GND"), ("C2", "+3V3", "GND"),
                             ("C3", "+3V3", "GND"), ("C4", "+3V3", "GND"),
                             ("C5", "EN", "GND"), ("C6", "+3V3", "GND"),
                             ("C7", "+3V3", "GND"), ("C8", "+3V3", "GND"),
                             ("C9", "+3V3", "GND"), ("C10", "EN", "GND")):
        connect(ref, "1", left)
        connect(ref, "2", right)
    connect("D1", "1", "LED_A")
    connect("D1", "2", "GND")
    connect_all("SW1", "1", "BOOT")
    connect_all("SW1", "2", "GND")
    connect_all("SW2", "1", "EN")
    connect_all("SW2", "2", "GND")
    # Espressif two-NPN, cross-coupled automatic boot/reset circuit.
    for ref, pin, name in (("Q1", "1", "Q1_BASE"), ("Q1", "2", "AUTO_RTS"),
                           ("Q1", "3", "EN"), ("Q2", "1", "Q2_BASE"),
                           ("Q2", "2", "AUTO_DTR"), ("Q2", "3", "BOOT")):
        connect(ref, pin, name)

    # Power backbone: short local traces from each supply pin to dedicated
    # In2.Cu plane vias. This avoids long, high-current 3V3 traces on F.Cu.
    p3 = nets["+3V3"]
    power_via(board, p3, 22.0, 38.0)
    route(board, p3, ((14.85, 38.0), (22.0, 38.0)), 0.60)
    route(board, p3, ((21.15, 38.0), (22.0, 38.0)), 0.80)
    route(board, p3, ((24.05, 38.0), (22.0, 38.0)), 0.50)
    power_via(board, p3, 27.5, 32.0)
    route(board, p3, ((25.225, 34.0), (25.225, 32.0), (27.5, 32.0)), 0.35)
    power_via(board, p3, 37.86, 33.0)
    route(board, p3, ((37.86, 31.75), (37.86, 33.0)), 0.35)
    power_via(board, p3, 49.0, 40.4)
    route(board, p3, ((50.225, 41.0), (50.225, 40.4), (49.0, 40.4)), 0.25)
    route(board, p3, ((50.225, 44.0), (49.0, 44.0), (49.0, 40.4)), 0.25)
    route(board, p3, ((54.1, 40.458), (53.0, 40.458), (53.0, 40.1),
                      (50.225, 40.1), (50.225, 41.0)), 0.20)

    # USB-C CC sink resistors. These low-speed lines are intentionally kept
    # separate from the D+/D- corridor used later for the differential pair.
    signal_via(board, nets["USB_CC1"], 3.5, 26.25)
    signal_via(board, nets["USB_CC1"], 8.175, 9.0)
    route(board, nets["USB_CC1"], ((1.655, 26.25), (3.5, 26.25)), 0.20)
    route(board, nets["USB_CC1"], ((3.5, 26.25), (8.5, 26.25),
                                   (8.5, 9.0), (8.175, 9.0)), 0.20, pcbnew.B_Cu)
    route(board, nets["USB_CC1"], ((8.175, 9.0), (8.175, 11.0)), 0.20)
    route(board, nets["USB_CC2"], ((1.655, 23.25), (4.0, 23.25),
                                   (4.0, 14.0), (8.175, 14.0)), 0.20)

    # Four-layer stackup: inner one is uninterrupted GND, inner two distributes
    # 3V3. Bottom GND is added for return-current continuity and stitching.
    copper_plane(board, nets["GND"], pcbnew.F_Cu)
    copper_plane(board, nets["GND"], pcbnew.In1_Cu)
    copper_plane(board, nets["+3V3"], pcbnew.In2_Cu)
    copper_plane(board, nets["GND"], pcbnew.B_Cu)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    text(board, "EventMonitor Audio Node", 32.5, 2.5, 1.5)
    text(board, "REV-A / 4L / POWER PLANES - UNROUTED", 32.5, 47.5, 1.0)
    target = OUT / "eventmonitor_audio_node_rev_a.kicad_pcb"
    target.parent.mkdir(exist_ok=True)
    board.Save(str(target))
    return target


if __name__ == "__main__":
    print(make())

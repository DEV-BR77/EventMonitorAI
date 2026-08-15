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


def make() -> Path:
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    edge(board, 65, 50)
    nets = {}
    for name in ("GND", "+3V3", "USB_5V", "USB_D+", "USB_D-", "USB_CC1", "USB_CC2",
                 "UART_TX_ESP", "UART_RX_ESP", "UART_RX_CP", "UART_TX_CP", "EN", "BOOT",
                 "I2S_WS", "I2S_BCLK", "I2S_DATA", "U2_RST", "AUTO_DTR", "AUTO_RTS",
                 "LED_STATUS", "LED_A"):
        item = pcbnew.NETINFO_ITEM(board, name)
        board.Add(item)
        nets[name] = item
    # x/y are deliberate Rev-A locations, not arbitrary quote coordinates.
    parts = (
        ("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J1", "USB-C USB2.0", 4.5, 25, 90),
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
    )
    for ref, value, x, y in passive:
        load(board, "Resistor_SMD", "R_0603_1608Metric", ref, value, x, y)
    caps = (
        ("C1", "10u VIN", 14, 34), ("C2", "10u VOUT", 23, 34),
        ("C3", "100n U3", 26, 34), ("C4", "100n U1", 35, 15),
        ("C5", "100n EN", 30, 38), ("C6", "1u MIC", 51, 41),
        ("C7", "100n MIC", 51, 44), ("C8", "4u7 U2", 20, 14),
        ("C9", "100n U2", 24, 14),
    )
    for ref, value, x, y in caps:
        load(board, "Capacitor_SMD", "C_0805_2012Metric" if ref in {"C1", "C2", "C8"} else "C_0603_1608Metric", ref, value, x, y)
    for ref, x, y in (("Q1", 29, 28), ("Q2", 35, 28)):
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
    for pad in ("A1", "A12", "B1", "B12", "SH"):
        connect("J1", pad, "GND")
    for pad in ("A4", "A9", "B4", "B9"):
        connect("J1", pad, "USB_5V")
    for pad, name in (("A5", "USB_CC1"), ("B5", "USB_CC2"), ("A6", "USB_D+"),
                      ("B6", "USB_D+"), ("A7", "USB_D-"), ("B7", "USB_D-")):
        connect("J1", pad, name)
    for pad, name in (("1", "USB_D+"), ("6", "USB_D+"), ("3", "USB_D-"),
                      ("4", "USB_D-"), ("2", "GND"), ("5", "USB_5V")):
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
    for pad, name in (("1", "USB_5V"), ("2", "+3V3"), ("3", "GND")):
        connect("U3", pad, name)

    # Passive network assignments. R6/R7 remain no-fit USB damping options
    # until the impedance calculation locks their exact position.
    for ref, net in (("R1", "USB_CC1"), ("R2", "USB_CC2"), ("R3", "EN"),
                     ("R4", "BOOT"), ("R5", "LED_STATUS"), ("R8", "UART_TX_ESP"),
                     ("R9", "UART_RX_ESP"), ("R10", "U2_RST")):
        connect(ref, "1", net)
    for ref, net in (("R1", "GND"), ("R2", "GND"), ("R3", "+3V3"),
                     ("R4", "+3V3"), ("R5", "LED_A"), ("R8", "UART_RX_CP"),
                     ("R9", "UART_TX_CP"), ("R10", "+3V3")):
        connect(ref, "2", net)
    for ref, left, right in (("C1", "USB_5V", "GND"), ("C2", "+3V3", "GND"),
                             ("C3", "+3V3", "GND"), ("C4", "+3V3", "GND"),
                             ("C5", "EN", "GND"), ("C6", "+3V3", "GND"),
                             ("C7", "+3V3", "GND"), ("C8", "+3V3", "GND"),
                             ("C9", "+3V3", "GND")):
        connect(ref, "1", left)
        connect(ref, "2", right)
    connect("D1", "1", "LED_A")
    connect("D1", "2", "GND")
    connect_all("SW1", "1", "BOOT")
    connect_all("SW1", "2", "GND")
    connect_all("SW2", "1", "EN")
    connect_all("SW2", "2", "GND")

    text(board, "EventMonitor Audio Node", 32.5, 2.5, 1.5)
    text(board, "REV-A / 4L / NETS ASSIGNED - UNROUTED", 32.5, 47.5, 1.0)
    target = OUT / "eventmonitor_audio_node_rev_a.kicad_pcb"
    target.parent.mkdir(exist_ok=True)
    board.Save(str(target))
    return target


if __name__ == "__main__":
    print(make())

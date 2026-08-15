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
    text(board, "EventMonitor Audio Node", 32.5, 2.5, 1.5)
    text(board, "REV-A / 4L / NOT FOR FABRICATION", 32.5, 47.5, 1.0)
    target = OUT / "eventmonitor_audio_node_rev_a.kicad_pcb"
    target.parent.mkdir(exist_ok=True)
    board.Save(str(target))
    return target


if __name__ == "__main__":
    print(make())

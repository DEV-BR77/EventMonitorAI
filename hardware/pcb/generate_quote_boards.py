"""Generate JLCPCB quote-only KiCad boards and fabrication archives.

The carrier board is a routed prototype.  The SMD boards are intentionally
quote templates (outline/BOM/CPL only), not production release designs.
"""
from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import pcbnew

ROOT = Path(__file__).parent
OUT = ROOT / "generated"


def v(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    item = pcbnew.NETINFO_ITEM(board, name)
    board.Add(item)
    return item


def pad(fp: pcbnew.FOOTPRINT, number: str, x: float, y: float, signal: pcbnew.NETINFO_ITEM | None) -> pcbnew.PAD:
    item = pcbnew.PAD(fp)
    item.SetNumber(number)
    item.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    item.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    item.SetSize(v(1.9, 1.9))
    item.SetDrillSize(v(1.0, 1.0))
    item.SetPosition(v(x, y))
    if signal is not None:
        item.SetNet(signal)
    fp.Add(item)
    return item


def track(board: pcbnew.BOARD, signal: pcbnew.NETINFO_ITEM, a: tuple[float, float], b: tuple[float, float], layer: int = pcbnew.F_Cu) -> None:
    item = pcbnew.PCB_TRACK(board)
    item.SetStart(v(*a))
    item.SetEnd(v(*b))
    item.SetWidth(pcbnew.FromMM(0.4))
    item.SetLayer(layer)
    item.SetNet(signal)
    board.Add(item)


def outline(board: pcbnew.BOARD, width: float, height: float) -> None:
    points = [(0, 0), (width, 0), (width, height), (0, height), (0, 0)]
    for start, end in zip(points, points[1:]):
        item = pcbnew.PCB_SHAPE(board)
        item.SetShape(pcbnew.SHAPE_T_SEGMENT)
        item.SetStart(v(*start))
        item.SetEnd(v(*end))
        item.SetLayer(pcbnew.Edge_Cuts)
        item.SetWidth(pcbnew.FromMM(0.25))
        board.Add(item)


def carrier() -> Path:
    board = pcbnew.BOARD()
    signals = {name: net(board, name) for name in ("+3V3", "GND", "I2S_WS", "I2S_SCK", "I2S_SD")}
    outline(board, 70, 60)
    left = pcbnew.FOOTPRINT(board); left.SetReference("J1")
    right = pcbnew.FOOTPRINT(board); right.SetReference("J2")
    mic = pcbnew.FOOTPRINT(board); mic.SetReference("J3")
    # Freenove board: 2x20, 2.54-mm grid, 22.86-mm row separation.
    for number in range(1, 21):
        signal = signals["+3V3"] if number == 1 else signals["I2S_WS"] if number == 3 else signals["I2S_SCK"] if number == 4 else signals["I2S_SD"] if number == 5 else None
        pad(left, str(number), 5, 5 + (number - 1) * 2.54, signal)
        pad(right, str(number), 27.86, 5 + (number - 1) * 2.54, signals["GND"] if number == 20 else None)
    board.Add(left); board.Add(right)
    # The shown INMP441 breakout is a 2x3 header: upper row L/R, WS, SCK;
    # lower row VDD, SD, GND.  L/R is tied to ground for the left I2S slot.
    mic_pins = (("L/R", "GND", 50, 15), ("WS", "I2S_WS", 52.54, 15),
                ("SCK", "I2S_SCK", 55.08, 15), ("VDD", "+3V3", 50, 17.54),
                ("SD", "I2S_SD", 52.54, 17.54), ("GND", "GND", 55.08, 17.54))
    for number, (_, name, x, y) in enumerate(mic_pins, start=1):
        pad(mic, str(number), x, y, signals[name])
    board.Add(mic)
    # GPIO4/5/6 and power rails from the documented Freenove pin positions.
    routes = {
        "+3V3": ((5, 5), (42, 5), (42, 17.54), (50, 17.54)),
        "I2S_WS": ((5, 10.08), (44, 10.08), (44, 15), (52.54, 15)),
        "I2S_SCK": ((5, 12.62), (46, 12.62), (46, 15), (55.08, 15)),
        "I2S_SD": ((5, 15.16), (48, 15.16), (48, 17.54), (52.54, 17.54)),
    }
    for name, points in routes.items():
        for a, b in zip(points, points[1:]):
            track(board, signals[name], a, b)
    track(board, signals["GND"], (27.86, 53.26), (50, 15), pcbnew.B_Cu)
    track(board, signals["GND"], (50, 15), (55.08, 17.54), pcbnew.B_Cu)
    target = OUT / "carrier" / "eventmonitor_audio_carrier.kicad_pcb"
    target.parent.mkdir(parents=True, exist_ok=True)
    board.Save(str(target))
    return target


def quote_template(name: str, size: tuple[int, int], bom: list[tuple[str, str, str]]) -> Path:
    board = pcbnew.BOARD(); outline(board, *size)
    target = OUT / name / f"{name}.kicad_pcb"; target.parent.mkdir(parents=True, exist_ok=True); board.Save(str(target))
    with (target.parent / "BOM.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file); writer.writerow(("Designator", "Comment", "Footprint")); writer.writerows(bom)
    with (target.parent / "CPL.csv").open("w", newline="", encoding="utf-8") as file:
        csv.writer(file).writerow(("Designator", "Mid X", "Mid Y", "Layer", "Rotation"))
    return target


def add_footprint(board: pcbnew.BOARD, library: str, name: str, reference: str,
                  value: str, x: float, y: float, rotation: float = 0) -> None:
    """Add a real KiCad footprint so JLC's viewer shows the SMD population.

    This quote package intentionally has no copper routing/netlist.  It is for
    PCB/PCBA pricing and placement checking, not a fabrication release.
    """
    # Use absolute .pretty paths: standalone kicad-cli Python does not load a
    # global fp-lib-table on every Windows installation.
    library_path = Path(r"E:\Apps\KiCad\share\kicad\footprints") / f"{library}.pretty"
    item = pcbnew.FootprintLoad(str(library_path), name)
    if item is None:
        raise RuntimeError(f"KiCad footprint not found: {library}:{name}")
    item.SetReference(reference)
    item.SetValue(value)
    item.SetPosition(v(x, y))
    item.SetOrientationDegrees(rotation)
    board.Add(item)


def native_usb_smd_quote() -> Path:
    """Native-USB, external-antenna SMD layout for JLCPCB price quotations.

    The external antenna is a U.FL pigtail to an enclosure-mounted RP-SMA
    bulkhead.  It is not an assembly component and consequently has no CPL row.
    """
    name = "smd_native_usb_external_antenna_quote"
    board = pcbnew.BOARD()
    outline(board, 65, 50)
    # ESP antenna edge on the right: keep the area right of the module free in
    # the final routed revision.  This placement image makes that constraint
    # visible in the JLC viewer without pretending that it is electrically done.
    parts = (
        ("RF_Module", "ESP32-S3-WROOM-1U", "U1", "ESP32-S3-WROOM-1U-N16R8", 42, 25, 90),
        ("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J1", "USB-C (power + native USB)", 8, 25, 90),
        ("Connector_Coaxial", "U.FL_Hirose_U.FL-R-SMT-1_Vertical", "J2", "U.FL antenna connector", 55, 8, 0),
        ("Sensor_Audio", "InvenSense_ICS-43434-6_3.5x2.65mm", "U2", "ICS-43434 I2S microphone", 48, 41, 0),
        ("Package_TO_SOT_SMD", "SOT-223-3_TabPin2", "U3", "AMS1117-3.3", 20, 36, 0),
        ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A", "SW1", "BOOT (GPIO0)", 29, 40, 0),
        ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A", "SW2", "RESET (EN)", 35, 40, 0),
        ("LED_SMD", "LED_0603_1608Metric", "D1", "Status LED green", 28, 14, 0),
        ("Resistor_SMD", "R_0603_1608Metric", "R1", "5.1 kΩ CC1", 14, 13, 0),
        ("Resistor_SMD", "R_0603_1608Metric", "R2", "5.1 kΩ CC2", 14, 16, 0),
        ("Resistor_SMD", "R_0603_1608Metric", "R3", "10 kΩ EN pull-up", 26, 34, 0),
        ("Resistor_SMD", "R_0603_1608Metric", "R4", "10 kΩ GPIO0 pull-up", 32, 34, 0),
        ("Resistor_SMD", "R_0603_1608Metric", "R5", "1 kΩ LED", 28, 17, 0),
        ("Resistor_SMD", "R_0603_1608Metric", "R6", "22 Ω USB D+ reserve", 17, 21, 0),
        ("Resistor_SMD", "R_0603_1608Metric", "R7", "22 Ω USB D- reserve", 17, 24, 0),
        ("Capacitor_SMD", "C_0805_2012Metric", "C1", "10 µF / 10 V regulator input", 19, 31, 0),
        ("Capacitor_SMD", "C_0805_2012Metric", "C2", "22 µF / 6.3 V regulator output", 23, 31, 0),
        ("Capacitor_SMD", "C_0805_2012Metric", "C3", "100 nF 3V3", 36, 31, 0),
        ("Capacitor_SMD", "C_0805_2012Metric", "C4", "100 nF microphone", 48, 37, 0),
        ("Capacitor_SMD", "C_0805_2012Metric", "C5", "1 µF EN", 26, 37, 0),
        ("MountingHole", "MountingHole_2.7mm_M2.5_DIN965_Pad", "H1", "M2.5 enclosure hole", 4, 4, 0),
        ("MountingHole", "MountingHole_2.7mm_M2.5_DIN965_Pad", "H2", "M2.5 enclosure hole", 61, 4, 0),
        ("MountingHole", "MountingHole_2.7mm_M2.5_DIN965_Pad", "H3", "M2.5 enclosure hole", 4, 46, 0),
        ("MountingHole", "MountingHole_2.7mm_M2.5_DIN965_Pad", "H4", "M2.5 enclosure hole", 61, 46, 0),
    )
    for part in parts:
        add_footprint(board, *part)
    target = OUT / name / f"{name}.kicad_pcb"
    target.parent.mkdir(parents=True, exist_ok=True)
    board.Save(str(target))
    bom = (
        ("U1", 1, "ESP32-S3-WROOM-1U-N16R8 (external antenna; replaces invalid N16R8-H4 designation)", "RF_Module:ESP32-S3-WROOM-1U", "SMD", "Verify current LCSC/JLC stock"),
        ("U2", 1, "ICS-43434 I²S MEMS microphone", "Sensor_Audio:InvenSense_ICS-43434-6_3.5x2.65mm", "SMD", "Bottom acoustic port; keep aperture clear"),
        ("U3", 1, "AMS1117-3.3, SOT-223", "Package_TO_SOT_SMD:SOT-223-3_TabPin2", "SMD", "Thermal copper required in routed revision"),
        ("J1", 1, "USB-C receptacle, USB2.0 + 5V", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "SMD", "Native USB: GPIO19/20"),
        ("J2", 1, "U.FL / I-PEX MHF1 board connector", "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "SMD", "Use separate U.FL-to-RP-SMA bulkhead pigtail"),
        ("SW1,SW2", 2, "SMD tactile button, BOOT / RESET", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", "SMD", ""),
        ("D1", 1, "Green LED 0603", "LED_SMD:LED_0603_1608Metric", "SMD", ""),
        ("R1,R2", 2, "5.1 kΩ 0603 USB-C CC pull-down", "Resistor_SMD:R_0603_1608Metric", "SMD", ""),
        ("R3,R4", 2, "10 kΩ 0603 EN / GPIO0 pull-up", "Resistor_SMD:R_0603_1608Metric", "SMD", ""),
        ("R5", 1, "1 kΩ 0603 LED resistor", "Resistor_SMD:R_0603_1608Metric", "SMD", ""),
        ("R6,R7", 2, "22 Ω 0603 USB data series reserve", "Resistor_SMD:R_0603_1608Metric", "SMD", "Fit only after USB SI check"),
        ("C1", 1, "10 µF 0805 10V X5R", "Capacitor_SMD:C_0805_2012Metric", "SMD", ""),
        ("C2", 1, "22 µF 0805 6.3V X5R", "Capacitor_SMD:C_0805_2012Metric", "SMD", ""),
        ("C3,C4", 2, "100 nF 0805 X7R", "Capacitor_SMD:C_0805_2012Metric", "SMD", ""),
        ("C5", 1, "1 µF 0805 X7R", "Capacitor_SMD:C_0805_2012Metric", "SMD", ""),
        ("H1,H2,H3,H4", 4, "M2.5 plated enclosure mounting holes", "MountingHole:MountingHole_2.7mm_M2.5_DIN965_Pad", "PCB", "No PCBA placement"),
        ("PIGTAIL", 1, "U.FL to RP-SMA female bulkhead cable", "External cable", "USER SUPPLIED", "Not placed by JLC"),
    )
    with (target.parent / "BOM.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("Designator", "Quantity", "Comment", "Footprint", "Assembly", "Note"))
        writer.writerows(bom)
    with (target.parent / "CPL.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("Designator", "Mid X", "Mid Y", "Layer", "Rotation"))
        for library, footprint, reference, value, x, y, rotation in parts:
            if not reference.startswith("H"):
                writer.writerow((reference, f"{x:.3f}", f"{y:.3f}", "T", f"{rotation:.1f}"))
    return target


def gerber(board: Path) -> None:
    target = board.parent / "gerbers"; target.mkdir(exist_ok=True)
    cli = Path(r"E:\Apps\KiCad\bin\kicad-cli.exe")
    subprocess.run([str(cli), "pcb", "export", "gerbers", "--layers", "F.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts", "--output", str(target), str(board)], check=True)
    subprocess.run([str(cli), "pcb", "export", "drill", "--output", str(target), str(board)], check=True)
    shutil.make_archive(str(board.parent / f"{board.stem}-JLCPCB"), "zip", target)


if __name__ == "__main__":
    routed = carrier(); gerber(routed)
    with (OUT / "carrier" / "BOM.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file); writer.writerow(("Designator", "Quantity", "Comment", "Footprint"))
        writer.writerows((("J1", 1, "Female socket header 1x20, 2.54 mm", "PinSocket_1x20_P2.54mm_Vertical"),
                          ("J2", 1, "Female socket header 1x20, 2.54 mm", "PinSocket_1x20_P2.54mm_Vertical"),
                          ("J3", 1, "Female socket header 2x3, 2.54 mm", "PinSocket_2x03_P2.54mm_Vertical")))
    with (OUT / "carrier" / "CPL.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("Designator", "Mid X", "Mid Y", "Layer", "Rotation"))
        writer.writerows((("J1", "5.000", "29.130", "T", "0"),
                          ("J2", "27.860", "29.130", "T", "0"),
                          ("J3", "52.540", "16.270", "T", "0")))
    quote_template("smd_no_battery_quote", (55, 45), [("U1", "ESP32-S3-WROOM-1-N16R8", "RF_Module:ESP32-S3-WROOM-1"), ("U2", "INMP441", "Mic module")])
    quote_template("smd_lipo_quote", (65, 50), [("U1", "ESP32-S3-WROOM-1-N16R8", "RF_Module:ESP32-S3-WROOM-1"), ("U2", "INMP441", "Mic module"), ("J1", "JST-PH-2 LiPo", "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical")])
    smd = native_usb_smd_quote(); gerber(smd)

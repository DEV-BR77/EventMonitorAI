# JLCPCB-Kalkulationspakete

`generated/carrier/eventmonitor_audio_carrier-JLCPCB.zip` ist ein zweilagiger,
gerouteter Rev-A-Prototyp fuer das Freenove ESP32-S3 N16R8 Board und einen
INMP441-Stecksockel. Vor Bestellung sind die tatsaechlichen Header-Mittelpunkte
und die Pinreihenfolge des gekauften Mikrofons mit dem Messschieber zu pruefen.

Die beiden SMD-Verzeichnisse sind Preisvorlagen mit finaler Umrissgroesse, BOM und
CPL-Schema. Sie sind **nicht** als Fertigungsfreigabe gedacht: USB-C, ESD,
Stromversorgung, Antennen-Freihaltezone sowie bei LiPo die Schutz- und
Ladeschaltung werden erst nach Auswahl des konkreten Akkus final geroutet.

## Native-USB-SMD-Platine mit externer Antenne (Kalkulation)

`generated/smd_native_usb_external_antenna_quote/` enthält die aktuelle
Kalkulationsmappe ohne Steckfassungen:

- `smd_native_usb_external_antenna_quote-JLCPCB.zip` – Gerberarchiv für den
  PCB-Preisrechner;
- `BOM.csv` – Stückliste einschließlich Montagehinweisen;
- `CPL.csv` – Bestückungskoordinaten für JLCPCB;
- `board-preview.png` – reine Sichtprüfung der Bauteilplatzierung.

Die Platine ist 65 × 50 mm groß und enthält das externe-Antennenmodul
`ESP32-S3-WROOM-1U-N16R8`, einen direkt aufgelöteten ICS-43434-I²S-MEMS-Sensor,
USB-C für 5 V und natives USB (GPIO19/GPIO20), AMS1117-3.3, BOOT/RESET,
Status-LED, U.FL und vier M2.5-Gehäusebohrungen. Das RP-SMA-Teil ist bewusst
kein Platinenbauteil: Es ist ein U.FL-auf-RP-SMA-Bulkhead-Pigtail, das später im
Gehäuse verschraubt wird.

Wichtig: `ESP32-S3-WROOM-1-N16R8-H4` ist keine einzelne Espressif-Variante.
`N16R8` (16 MB Flash, 8 MB PSRAM) und `H4` sind unterschiedliche
Speicher-/Temperaturvarianten. Für die gewünschte RP-SMA-Antenne ist die
`1U`-Variante erforderlich. Diese Mappe ist absichtlich als **QUOTE ONLY –
NOT FOR MANUFACTURING** angelegt: Vor einer Fertigungsfreigabe fehlen noch
Schaltplan/Netzliste, USB-ESD-Schutz, vierlagiges Impedanz- und RF-Routing,
Mikrofon-Akustiköffnung sowie DRC/ERC und ein Musteraufbau.

# Audio-Transport und Gerätetelemetrie

ESP32-S3-Sensoren senden UDP-Datagramme mit einem 32 Byte großen
EventMonitorAI-Header vor den PCM-Samples. Das Protokoll enthält eine stabile,
aus der eFuse-MAC abgeleitete Geräte-ID, Sequenznummer, Laufzeit, Samplerate,
Sample-Anzahl, Paket-Peak sowie die Firmwareversion.

Der Raspberry-Pi-Empfänger erkennt ausgelassene Sequenznummern einschließlich
des 32-Bit-Wraparounds. Empfangene und verlorene Pakete werden regelmäßig über
den geschützten Telemetrie-Endpunkt an das Backend gemeldet. Das Dashboard
zeigt Online-Status, Firmware, Quell-IP, Paketverlust, Samplerate und Peak.

Während der Firmwaremigration akzeptiert der Empfänger weiterhin bisherige
Pakete, die ausschließlich aus 16-Bit-PCM bestehen. Diese Legacy-Quellen
liefern Audio, aber keine stabile ID oder Transporttelemetrie.

## Binärformat Version 1

Alle Mehrbyte-Werte verwenden Little Endian. Die Nutzlast enthält
`sample_count` vorzeichenbehaftete 16-Bit-Samples.

| Feld | Typ | Bedeutung |
|---|---|---|
| magic | 4 Byte | `EMAI` |
| protocol_version | uint8 | aktuell `1` |
| flags | uint8 | reserviert |
| header_size | uint16 | aktuell `32` |
| device_id | uint64 | ESP32-eFuse-MAC |
| sequence | uint32 | fortlaufende Sendeversuche |
| uptime_ms | uint32 | Gerätelebenszeit |
| sample_rate | uint16 | Samples pro Sekunde |
| sample_count | uint16 | Samples in der Nutzlast |
| peak | uint16 | höchster Absolutwert im Paket |
| firmware_version | uint16 | komprimiertes SemVer |

## Ereignisclips mit Vorlauf

Parallel zum Live-Stream hält der ESP32-S3 im PSRAM die letzten zwei Sekunden
16-kHz-Mono-PCM. Ein Peak-Trigger übernimmt diesen vollständigen Ringpuffer und
zeichnet drei Sekunden Nachlauf auf. Der resultierende WAV-Clip besitzt exakt
80.000 Samples beziehungsweise fünf Sekunden Dauer.

Der Clip wird nicht als fragmentiertes UDP-Paket, sondern in einem getrennten
FreeRTOS-Task per HTTP an Port 12346 des Raspberry Pi übertragen. Dadurch läuft der
UDP-Audiostream während des Uploads weiter. Der Request enthält stabile Geräte-ID,
lokale Ereignisnummer, Trigger-Uptime und einen gemeinsamen geheimen Token.

Der Pi akzeptiert ausschließlich authentifizierte 16-Bit-Mono-WAVs mit 16 kHz und
einer Dauer zwischen einer und zehn Sekunden. Erfolgreiche Uploads werden atomar
unter `/var/lib/eventmonitor/clips` abgelegt. Eine JSON-Sidecar-Datei dokumentiert
Gerät, Ereignis, Quell-IP, Empfangszeit, Audioformat und SHA-256-Prüfsumme.

Als ausfallsichere zweite Quelle hält das Backend je Gerät 20 Sekunden des laufenden
PCM-Stroms ausschließlich im Arbeitsspeicher. Liegt beim Eintreffen eines Ereignisses
noch kein ESP32-Clip vor, schneidet es den tatsächlichen Ereigniszeitraum mit je einer
Sekunde Vor- und Nachlauf aus diesem Puffer. Dauert der Ausschnitt länger als zehn
Sekunden, wird das Fenster um den stärksten Sample-Ausschlag positioniert. Dadurch
bleiben insbesondere kurze Schläge und der laute Beginn eines Schreis hörbar, obwohl
der Pi ein Ereignis erst nach drei Sekunden Ruhe abschließt.

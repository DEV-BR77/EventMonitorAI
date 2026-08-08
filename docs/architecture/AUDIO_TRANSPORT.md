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

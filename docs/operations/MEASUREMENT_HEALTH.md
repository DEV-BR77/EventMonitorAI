# Messkettenstatus und Ausfallprüfung

Der globale Status im Dashboard-Kopf wird alle 30 Sekunden aus der vorhandenen
Gerätetelemetrie aktualisiert. Er ist auf jeder Dashboard-Seite sichtbar:

- **grün:** alle aktivierten Mikrofone haben innerhalb der letzten 90 Sekunden
  Telemetrie gesendet;
- **gelb:** nur ein Teil der aktivierten Mikrofone ist online oder es ist kein
  Mikrofon aktiviert;
- **rot:** kein aktiviertes Mikrofon sendet oder die Dashboard-API ist nicht
  erreichbar.

Administratoren gelangen durch Anklicken des Status direkt zur Seite
**Mikrofone**. Dort bleiben Zeitstempel, Firmware, Quelladresse, Paketverlust,
Samplerate, Peak und aktueller Pegel je Gerät sichtbar.

## Datenweg

`ESP32 -> UDP 12345 -> Raspberry Pi 192.168.178.194 -> EventMonitorAI :8015 -> PostgreSQL -> Dashboard`

Der Empfänger besitzt zusätzlich die dauerhaft konfigurierte Adresse
`192.168.178.64`, damit bereits installierte Firmware bis zum nächsten Flashen
weiterarbeiten kann. Neue Firmware verwendet ausschließlich `.194`.

## Prüfung bei rotem Status

1. In **Mikrofone** den letzten Telemetriezeitpunkt beider Geräte vergleichen.
2. Auf dem Raspberry Pi den Dienst `eventmonitor-receiver` und UDP-Port 12345
   prüfen.
3. Sicherstellen, dass `.194` und die Kompatibilitätsadresse `.64` am Interface
   `eth0` vorhanden sind.
4. Erst danach API, Datenbank und Dashboard untersuchen. Ein grüner `/health`-
   Endpunkt allein beweist nicht, dass Audiodaten eingehen.

## Vorfall vom 17. August 2026

Dashboard, API und Datenbank waren verfügbar, aber beide ESP32 sendeten noch an
die nicht mehr vorhandene Adresse `.64`. Dadurch blieben Telemetrie und Ereignisse
leer. Die sekundäre Adresse wurde auf dem aktiven Empfänger `.194` wiederhergestellt
und über NetworkManager neustartfest gespeichert. Danach sendeten beide Geräte
wieder im Zwei-Sekunden-Takt und die API nahm Audiofenster an.

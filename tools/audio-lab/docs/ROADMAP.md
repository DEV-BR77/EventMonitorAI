# Roadmap

## v0.2 – Historischer Import und manuelles Labeling

- ZIP- und Ordnerimport
- SQLite-Datenbank
- Dublettenprüfung
- Segmentierung
- Priorisierung nach Pegelauffälligkeit
- Audio-Player und manuelle Labels
- CSV-Export

## v0.3 – Importverwaltung

- [x] Importjournal mit Dateiname, Status und Fehlergrund
- [x] Wiederholungsfunktion für fehlgeschlagene Pakete
- Prüfung von Audio-/CSV-Dauer
- konfigurierbare Segmentlänge
- frei definierbare Kategorien
- Kalender- und Tagesansicht
- Backup- und Restore-Funktion

## v0.4 – Ereignisvisualisierung

- [x] dB-Zeitreihe je Aufnahme
- klickbare Peaks
- [x] Spektrogramm je Segment
- Frequenzmerkmale
- zusammenhängende Ereignisse statt isolierter Segmente
- Start-/Endgrenzen manuell korrigieren

## v0.5 – Lernsystem

- Audio-Feature-Extraktion
- Trainings- und Testdatensatz
- erstes lokales Basismodell
- Modellvorschläge in der Labeling-Oberfläche
- Bestätigen, Korrigieren oder Verwerfen
- Modellversionierung und Qualitätsmetriken

## v0.6 – Ähnlichkeitssuche

- Audio-Embeddings
- ähnliche historische Ereignisse finden
- Clusterbildung
- Stapelbestätigung ähnlicher Treffer

## v1.0 – Integration in EventMonitor

- gemeinsames Ereignis-API
- Live-Eingang vom Raspberry Pi oder ESP32
- regelbasierte Benachrichtigungen
- Home-Assistant-Anbindung
- lokales Dashboard
- nachvollziehbares Lärmprotokoll
- Benutzer- und Berechtigungskonzept

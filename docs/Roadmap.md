# EventMonitorAI Roadmap

Die Roadmap beschreibt die angestrebte Reihenfolge. Termine werden erst festgelegt, wenn Umfang und technische Risiken ausreichend geklärt sind.

## Phase 0 – Repository und Grundlagen

- [x] zentrale Projektstruktur
- [x] Architektur- und Entscheidungsdokumentation
- [x] Coding Guidelines und Contribution-Prozess
- [x] CI-Grundprüfung
- [x] Release-Workflow für saubere Quellcodepakete
- [ ] einheitliche Versionierung aller Komponenten
- [ ] reproduzierbare Entwicklungsumgebung

## Phase 1 – Stabile Ereigniserfassung

- [x] ESP32-S3 sendet Audio per UDP
- [x] Raspberry Pi verarbeitet Audiofenster
- [x] YAMNet-Klassifikation als Ausgangspunkt
- [x] FastAPI-Backend und Ereignisdatenbank
- [ ] robuste Wiederverbindung und Paketverlustbehandlung
- [ ] Geräteidentität, Health-Status und Telemetrie
- [ ] nachvollziehbare Audiopegel-Kalibrierung

## Phase 2 – EventMonitor AudioLab

- [x] ZIP- und Ordnerimport
- [x] Dublettenprüfung
- [x] Audio-/dB-Segmentierung
- [x] manuelles Labeling und CSV-Export
- [ ] Importprotokoll und Wiederaufnahme abgebrochener Imports
- [ ] interaktiver dB-Verlauf, Spektrogramm und Segmentnavigation
- [ ] variable Segmentgrenzen und Ereigniszuschnitt
- [ ] Backup und Datenmigration

## Phase 3 – Lernende Klassifizierung

- [ ] versionierte Feature- und Preprocessing-Pipeline
- [ ] Trainings-, Validierungs- und Testaufteilung nach Aufnahmen
- [ ] Basismodell und nachvollziehbare Qualitätsmetriken
- [ ] Modellvorschläge mit Bestätigung/Korrektur
- [ ] Active Learning für unsichere oder informative Beispiele
- [ ] Audio-Embeddings und Ähnlichkeitssuche
- [ ] lokale Modellverwaltung und Rollback

## Phase 4 – Ereignisse und Cases

- [ ] einzelne Segmente zu zusammenhängenden Ereignissen verbinden
- [ ] Schreien, Rufen und Impulse zeitlich gruppieren
- [ ] Case-Modell mit Beginn, Ende, Dauer und Teilereignissen
- [ ] Notizen, Bestätigungsstatus und revisionssichere Änderungshistorie
- [ ] Lärmprotokoll als CSV und PDF

## Phase 5 – Dashboard und Integration

- [ ] Kalender, Timeline, Heatmaps und Statistiken
- [ ] Live-Ereignisansicht
- [ ] Home-Assistant-Integration
- [ ] Benachrichtigungsregeln
- [ ] PostgreSQL-Option und Mehrgerätebetrieb
- [ ] Rollen, Authentifizierung und Zugriffsschutz

## Phase 6 – Produktreife

- [ ] Installationspakete und Upgrade-Strategie
- [ ] automatisierte Backups und Aufbewahrungsregeln
- [ ] Performance- und Langzeittests
- [ ] Security- und Datenschutzreview
- [ ] dokumentierte Release-Kriterien für v1.0

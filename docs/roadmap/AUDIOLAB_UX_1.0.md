# AudioLab UX 1.0

## Ziel

Verbesserung der Benutzerfreundlichkeit und Effizienz des Import-, Analyse- und Labeling-Workflows.

## Geplante Issues

### 1. Guided Workflow

Nach erfolgreichem Import soll AudioLab automatisch zur Analyse wechseln oder einen deutlich sichtbaren Button zum Start der Analyse anzeigen.

Akzeptanzkriterien:

- klarer Ablauf von Import über Analyse bis Labeling
- keine unnötige Seitennavigation
- verständliche nächste Aktion

### 2. Auto Save and Next Event

Nach dem Speichern einer Klassifizierung soll automatisch das nächste unbewertete Ereignis geöffnet werden.

Akzeptanzkriterien:

- Label wird gespeichert
- nächstes offenes Ereignis wird geladen
- Fortschritt wird als `Ereignis 1 von 100` dargestellt
- Navigation vor und zurück bleibt möglich

### 3. Import Progress

Bei langen Aufnahmen muss der Fortschritt sichtbar sein.

Akzeptanzkriterien:

- Fortschrittsbalken
- Anzahl verarbeiteter und gesamter Segmente
- Statusmeldung während des Imports
- optional geschätzte Restzeit

### 4. Resumable Import

Unterbrochene Importe sollen fortgesetzt werden können.

Akzeptanzkriterien:

- Zwischenstände werden regelmäßig gespeichert
- vorhandener Importstatus wird erkannt
- Benutzer kann einen Import fortsetzen oder neu starten

### 5. Flexible CSV Selection

Der Import darf nicht vom festen Dateinamen `db.csv` abhängig sein.

Akzeptanzkriterien:

- beliebiger CSV-Dateiname
- explizite Dateiauswahl oder zuverlässige automatische Erkennung
- verständliche Fehlermeldung bei ungültigem Format

### 6. Labeling Dashboard

Vor und während des Labelings soll eine Übersicht zum Fortschritt sichtbar sein.

Akzeptanzkriterien:

- gesamte Anzahl der Ereignisse
- Anzahl offen
- Anzahl bewertet
- Fortschritt in Prozent
- optionale Statistik nach Label
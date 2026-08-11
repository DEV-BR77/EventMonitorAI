# Architektur und Datenmodell

## Komponenten

```text
ZIP / Messordner
       │
       ▼
 Importer ─────► Audiobibliothek
       │
       ▼
 SQLite-Datenbank
       │
       ├─► Übersicht
       ├─► Labeling-Oberfläche
       ├─► Auswertung / CSV-Export
       └─► zukünftiges Modelltraining
```

## Python-Module

| Datei | Aufgabe |
|---|---|
| `app.py` | Streamlit-Oberfläche |
| `import_data.py` | Kommandozeilenimport |
| `eventmonitor/importer.py` | Dateierkennung, Parser, Import und Segmentbildung |
| `eventmonitor/db.py` | SQLite-Schema und Datenbankverbindung |
| `eventmonitor/visualization.py` | STFT-Spektrogramm und browsergerechte Datenreduktion |

## Datenbanktabellen

### `recordings`

Metadaten einer Aufnahme:

- Quellpfad
- SHA-256-Hash
- Pfad zur lokalen Audiokopie
- Aufnahmebeginn
- Dauer
- Abtastrate
- Kanalanzahl
- Importzeitpunkt

### `db_samples`

Zeitlich aufgelöste dB(A)-Messwerte:

- Offset zur Aufnahme
- Messzeitpunkt
- aktueller Pegel
- maximaler Pegel
- Durchschnittspegel

### `spectrum_bins`

Gesamtspektren aus den Extended-Dateien:

- linear oder logarithmisch
- Frequenz
- Minimum
- Maximum
- Durchschnitt

### `segments`

Zu prüfende Audioabschnitte:

- Start und Ende
- Peak und Mittelwert
- Auffälligkeit gegenüber dem Median-Grundpegel
- bestätigtes Label
- Sicherheit
- Notiz
- Labelzeitpunkt

### `predictions`

Für spätere Modellvorhersagen:

- Modellname und Version
- vorgeschlagene Kategorie
- Konfidenz
- Erstellungszeitpunkt

## Segmentbewertung

Die aktuelle Auffälligkeit wird vereinfacht berechnet als:

```text
Segment-Peak minus Median aller dB-Werte der Aufnahme
```

Das ist eine robuste erste Heuristik, ersetzt jedoch keine psychoakustische oder normgerechte Ereignisbewertung.

## Geplante Trennung

Langfristig sollten drei Ebenen getrennt werden:

1. **Rohmessung:** unveränderliche Originaldaten
2. **Akustisches Ereignis:** technisch erkannter Klangtyp
3. **Bewertung:** menschliche Bestätigung, Notiz und Relevanz

Damit bleibt nachvollziehbar, was gemessen, was vorgeschlagen und was tatsächlich bestätigt wurde.

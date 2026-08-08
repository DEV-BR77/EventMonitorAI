# EventMonitor AudioLab

**EventMonitor AudioLab** ist das lokale Import-, Analyse- und Lernmodul des Repositorys **EventMonitor**. Es führt historische Schallpegelmessungen, Audiodateien und Frequenzanalysen automatisiert in einer gemeinsamen Datenbank zusammen.

Der Schwerpunkt liegt auf der strukturierten Erkennung und manuellen Bestätigung relevanter akustischer Ereignisse, insbesondere:

- Schreien
- Rufen
- Streit oder mehrere laute Stimmen
- Schlagen und Aufprallgeräusche
- Türknallen
- Auto und Vorbeifahrt
- Motorrad
- Hupe

AudioLab ist zunächst ein **Human-in-the-Loop-System**: Das Tool bereitet auffällige Abschnitte vor, der Benutzer hört sie an und bestätigt oder korrigiert die Kategorie. Nur bestätigte Zuordnungen sollen später zum Training eigener Modelle verwendet werden.

## Funktionsumfang v0.2

- Import einzelner Messpakete als ZIP
- rekursiver Massenimport ganzer Ordner
- Unterstützung für WAV, MP3, FLAC, OGG und M4A
- Import von `db.csv`, `extended.csv` und `extended_logarithm.csv`
- automatische Dublettenprüfung über SHA-256
- zentrale SQLite-Datenbank
- automatische Aufteilung in 5-Sekunden-Segmente
- Priorisierung auffälliger und lauter Abschnitte
- integrierter Audio-Player
- manuelle Zuordnung und Bestätigung von Lärmarten
- CSV-Export als Lärmprotokoll
- lokale Verarbeitung ohne Cloud-Zwang

## Schnellstart unter Windows

1. Python 3.11 oder neuer installieren.
2. Repository klonen oder Projektordner herunterladen.
3. Im Ordner `tools/audio-lab` die Datei `start_windows.bat` starten.
4. Im Browser **Import** öffnen.
5. ZIP-Dateien oder einen vorhandenen Messordner importieren.
6. Unter **Ereignisse lernen** auffällige Segmente anhören und zuordnen.

Alternativ manuell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Empfohlene Repository-Struktur

```text
EventMonitor/
├─ README.md
├─ docs/
├─ tools/
│  └─ audio-lab/
│     ├─ app.py
│     ├─ import_data.py
│     ├─ start_windows.bat
│     ├─ requirements.txt
│     ├─ eventmonitor/
│     ├─ docs/
│     └─ README.md
└─ data/                 # nicht in Git einchecken
```

Die Dateien dieses Pakets gehören in `EventMonitor/tools/audio-lab/`.

## Import per Kommandozeile

Einzelnes Messpaket:

```powershell
python import_data.py "D:\Laermmessungen\Messung_001.zip"
```

Alle ZIP-Dateien eines Ordners rekursiv:

```powershell
python import_data.py "D:\Laermmessungen" --folder
```

## Dokumentation

- [Installation](docs/INSTALLATION.md)
- [Bedienungsanleitung](docs/BEDIENUNG.md)
- [Messdaten und Importformat](docs/IMPORTFORMAT.md)
- [Kategorien und Lernworkflow](docs/LABELING.md)
- [Architektur und Datenmodell](docs/ARCHITEKTUR.md)
- [Feature- und Preprocessing-Pipeline](docs/FEATURE_PIPELINE.md)
- [Trainings-, Validierungs- und Testaufteilung](docs/DATASET_SPLITS.md)
- [Basismodell und Qualitätsmetriken](docs/BASELINE_MODEL.md)
- [Modellvorschläge bestätigen und korrigieren](docs/MODEL_SUGGESTIONS.md)
- [Active Learning](docs/ACTIVE_LEARNING.md)
- [Audio-Embeddings und Ähnlichkeitssuche](docs/EMBEDDINGS.md)
- [Personenverwaltung und personenbezogene Ereignisse](docs/PEOPLE.md)
- [Lokale Modellverwaltung und Rollback](docs/MODEL_REGISTRY.md)
- [Zeitliche Ereignisgruppierung](docs/EVENT_GROUPING.md)
- [Cases und Teilereignisse](docs/CASES.md)
- [Case-Notizen, Status und Änderungshistorie](docs/CASE_AUDIT.md)
- [Lärmprotokoll als CSV und PDF](docs/NOISE_LOG.md)
- [Roadmap](docs/ROADMAP.md)

## Grenzen und verantwortungsvolle Nutzung

AudioLab klassifiziert akustische Muster. Es kann nicht sicher feststellen, welche konkrete Person ein Geräusch verursacht hat oder was außerhalb der Aufnahme tatsächlich geschehen ist. Ein erkannter Aufprall kann beispielsweise von einer Tür, einem Gegenstand oder einer anderen Quelle stammen.

Für nachvollziehbare Auswertungen sollten deshalb immer erhalten bleiben:

- unveränderte Originaldatei
- Import-Hash
- ursprünglicher Zeitstempel
- gemessener Pegel
- bestätigte Kategorie
- Unsicherheit und Notiz

Audioaufnahmen können rechtlich sensible Inhalte enthalten. Vor dauerhafter Aufzeichnung, Verarbeitung oder Weitergabe sollten die jeweils geltenden Datenschutz- und Persönlichkeitsrechte geprüft werden.

## Status

Aktueller Stand: **Prototyp v0.2**. Noch nicht als beweissichere, geeichte oder behördlich anerkannte Schallmesslösung einzusetzen.

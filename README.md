# EventMonitorAI

> **Lokale, datenschutzorientierte Plattform zur Erfassung, Analyse und lernenden Klassifizierung akustischer Ereignisse.**

EventMonitorAI verbindet ESP32-Audiosensoren, Raspberry-Pi-Edge-Verarbeitung, eine FastAPI-Ereignisplattform und **EventMonitor AudioLab** für historische Messungen. Ziel ist, große Mengen vorhandener und künftiger Lärmaufnahmen automatisch zu strukturieren, auffällige Abschnitte zu finden und durch bestätigte Zuordnungen schrittweise eine an die reale Umgebung angepasste Erkennung aufzubauen.

## Projektstatus

**Entwicklungsphase:** Alpha / aktiver Aufbau

Aktuell vorhanden:

- ESP32-S3-Audiosender per UDP
- Raspberry-Pi-Empfänger mit YAMNet-basierter Klassifizierung
- FastAPI-Backend mit SQLite-Ereignisdatenbank
- REST-Endpunkte für Health-Check und Ereignisse
- geschütztes Dashboard mit Kalender, Timeline, Heatmap, Statistiken und Live-Ansicht
- lokale Benutzerrollen, Mehrgerätebetrieb, Live-Sound-Freigaben, installierbare PWA und Push-Benachrichtigungen
- Home-Assistant-Webhook und optionale PostgreSQL-Datenbank
- deutsche Label- und Kategoriezuordnung
- EventMonitor AudioLab für ZIP-Massenimport, Segmentierung, Anhören, Labeling und CSV-Export

Noch nicht produktionsreif sind insbesondere die automatische Modellnachschulung,
belastbare Ereigniszusammenfassung, Beweissicherung, Datenbankmigrationen und das
abschließende Security-/Datenschutzreview.

## Schwerpunkt der Erkennung

Das System wird zunächst für folgende akustische Klassen optimiert:

- Schreien und lautes Rufen
- Streit oder mehrere laute Stimmen
- Schlagen, Klopfen und andere Aufprallgeräusche
- Türknallen
- Auto und Vorbeifahrt
- Motorrad
- Hupe

Zusätzliche Negativ- und Kontextklassen wie normales Sprechen, Hund, Musik, Maschinen, Wind oder Regen reduzieren Fehlalarme.

> EventMonitorAI erkennt akustische Muster. Es stellt nicht zweifelsfrei fest, welche Person oder Ursache ein Geräusch erzeugt hat. Automatische Ergebnisse bleiben Vorschläge, bis sie bestätigt wurden.

## Systemübersicht

```text
ESP32-S3 + INMP441
        │ UDP-Audio
        ▼
Raspberry Pi / Edge Receiver
        │ Ereignisse + Pegel + Modellresultate + flüchtiger Live-Audiostream
        ▼
FastAPI Backend ───────────────► SQLite / später PostgreSQL
        │
        ├── REST API
        ├── Live- und Ereignisdaten
        └── zukünftiges Dashboard

Historische ZIP-/Audio-Messungen
        │
        ▼
EventMonitor AudioLab
        ├── Massenimport und Dublettenprüfung
        ├── dB-/Audio-Segmentierung
        ├── Human-in-the-Loop-Labeling
        └── Trainings- und Lärmprotokoll-Daten
```

Detaillierte Beschreibung: [docs/Architecture.md](docs/Architecture.md)

## Repository-Struktur

```text
EventMonitorAI/
├── .github/                 GitHub-Workflows und Vorlagen
├── backend/                 FastAPI-Backend und Datenmodell
├── edge/raspberry-pi/       Edge-Empfänger und lokale Klassifizierung
├── firmware/                ESP32-S3-Firmware
├── tools/audio-lab/         Historischer Import und Lernoberfläche
├── docs/                    Architektur, Betrieb, Entwicklung und Roadmap
├── tests/                   automatisierte Tests
├── scripts/                 Entwickler- und Prüfskripte
├── models/                  lokale Modellablage, Inhalte nicht versioniert
├── exports/                 lokale Exporte, Inhalte nicht versioniert
└── logs/                    lokale Logs, Inhalte nicht versioniert
```

## Schnellstart: Backend

Voraussetzungen: Python 3.11 oder neuer.

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Danach:

- API-Dokumentation: `http://127.0.0.1:8000/docs`
- Health-Check: `http://127.0.0.1:8000/health`
- Dashboard: `http://127.0.0.1:8000/`

Ausführliche Anleitung: [docs/getting-started/INSTALLATION.md](docs/getting-started/INSTALLATION.md)

## Schnellstart: EventMonitor AudioLab

```powershell
cd tools\audio-lab
.\start_windows.bat
```

AudioLab öffnet eine lokale Browseroberfläche für Import, Wiedergabe, Labeling und Auswertung. Details: [tools/audio-lab/README.md](tools/audio-lab/README.md)

## Entwicklung

Vor Änderungen bitte lesen:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [docs/development/CODING_GUIDELINES.md](docs/development/CODING_GUIDELINES.md)
- [docs/development/BRANCHING_AND_RELEASES.md](docs/development/BRANCHING_AND_RELEASES.md)
- [SECURITY.md](SECURITY.md)

Lokale Qualitätsprüfung:

```powershell
py scripts/check_project.py
```

Die GitHub-CI prüft Python-Syntax, Tests, sensible Dateien und grundlegende Repository-Hygiene.

## Dokumentation

| Thema | Dokument |
|---|---|
| Installation | [docs/getting-started/INSTALLATION.md](docs/getting-started/INSTALLATION.md) |
| Architektur | [docs/Architecture.md](docs/Architecture.md) |
| Dashboard und Integrationen | [docs/PHASE5_DASHBOARD.md](docs/PHASE5_DASHBOARD.md) |
| AudioLab | [tools/audio-lab/README.md](tools/audio-lab/README.md) |
| Roadmap | [docs/Roadmap.md](docs/Roadmap.md) |
| Produkt-Backlog | [docs/ProductBacklog.md](docs/ProductBacklog.md) |
| Entscheidungen | [docs/DecisionLog.md](docs/DecisionLog.md) und [docs/adr/](docs/adr/) |
| Betrieb und Datenschutz | [docs/operations/PRIVACY_AND_DATA.md](docs/operations/PRIVACY_AND_DATA.md) |

## Leitprinzipien

1. **Privacy first** – lokale Verarbeitung und Datenkontrolle.
2. **Local first** – Kernfunktionen ohne Cloud-Zwang.
3. **Everything is an event** – ein gemeinsames Ereignismodell.
4. **Human in the loop** – bestätigte Labels statt blindem Selbstlernen.
5. **Simple before clever** – nachvollziehbare, testbare Schritte.
6. **Documentation matters** – Architektur und Entscheidungen werden dokumentiert.
7. **Quality over speed** – stabile Daten und reproduzierbare Ergebnisse.

## Lizenz

Siehe [LICENSE](LICENSE).

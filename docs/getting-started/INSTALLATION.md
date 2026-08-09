# Installation und lokaler Start

## Voraussetzungen

- Windows 10/11 oder Linux
- Python 3.11 oder neuer
- Git
- für ESP32-Firmware: VS Code mit PlatformIO
- für MP3/M4A-Verarbeitung gegebenenfalls FFmpeg

## Repository klonen

```powershell
git clone https://github.com/DEV-BR77/EventMonitorAI.git
cd EventMonitorAI
```

## Produktionsinstallation mit Docker Desktop

```powershell
.\scripts\install.ps1 -Build
```

Dashboard und API sind danach standardmäßig unter `http://127.0.0.1:8015`
erreichbar. Details zu Installation, Upgrade und Rollback stehen in
[`../operations/INSTALL_UPGRADE.md`](../operations/INSTALL_UPGRADE.md).

## Backend als Entwicklungsumgebung installieren

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Die lokale SQLite-Datenbank wird beim ersten Start unter `backend/data/` erzeugt und nicht von Git versioniert.

## AudioLab installieren

```powershell
cd ..\tools\audio-lab
.\start_windows.bat
```

Alternativ manuell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Qualitätsprüfung

Vom Repository-Stamm:

```powershell
py scripts/check_project.py
```

Optional mit Entwicklungsabhängigkeiten:

```powershell
pip install -r requirements-dev.txt
pytest
```

## Lokale Daten sichern

Folgende Ordner enthalten Laufzeitdaten und gehören nicht ins Repository:

- `backend/data/`
- `tools/audio-lab/data/`
- `models/`
- `exports/`
- `logs/`

Diese Ordner müssen separat gesichert werden, wenn Messungen oder bestätigte Labels erhalten bleiben sollen.

Der Docker-Produktionsbetrieb enthält einen automatischen Backupdienst. Siehe
[`../operations/BACKUP_RESTORE.md`](../operations/BACKUP_RESTORE.md).

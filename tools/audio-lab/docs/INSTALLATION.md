# Installation

## Voraussetzungen

- Windows 10 oder Windows 11
- Python 3.11 oder neuer
- mindestens 4 GB freier Speicher für Programm und Testdaten
- zusätzlicher Speicher entsprechend dem Umfang der Audiosammlung

Für MP3- und M4A-Dateien kann abhängig von der lokalen Python-/Audioinstallation zusätzlich FFmpeg erforderlich sein. WAV ist für technische Analysen das bevorzugte Format.

## Installation über das Startskript

1. Den Ordner `audio-lab` lokal ablegen.
2. `start_windows.bat` doppelklicken.
3. Beim ersten Start wird die virtuelle Python-Umgebung `.venv` angelegt.
4. Die Abhängigkeiten aus `requirements.txt` werden installiert.
5. Streamlit startet die Anwendung im Standardbrowser.

## Manuelle Installation

PowerShell im Projektordner öffnen:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## Datenverzeichnisse

Beim ersten Start entstehen lokal:

```text
data/
├─ eventmonitor.sqlite3
└─ library/
```

`eventmonitor.sqlite3` enthält Metadaten, dB-Messwerte, Segmente und Labels. Unter `library/` liegen die importierten Audiokopien.

Diese Verzeichnisse sollten nicht in Git eingecheckt werden. Empfohlene `.gitignore`-Einträge:

```gitignore
.venv/
__pycache__/
*.pyc
data/
.streamlit/
```

## Start nach der Installation

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

## Fehlerbehebung

### `python` oder `py` wurde nicht gefunden

Python installieren und die Option **Add Python to PATH** aktivieren.

### MP3 kann nicht gelesen werden

Die Datei zunächst in WAV konvertieren oder FFmpeg installieren. Die CSV-Dateien und die Audiodatei müssen gemeinsam im ZIP-Paket liegen.

### Browser öffnet sich nicht

Die in PowerShell angezeigte lokale Adresse manuell öffnen, normalerweise:

```text
http://localhost:8501
```

### Import meldet „bereits vorhanden“

Das ist die Dublettenprüfung. Dasselbe ZIP wurde anhand seines SHA-256-Hashes bereits importiert.

# Repository-Umstrukturierung

## Ausgangslage

Der hochgeladene Stand enthielt neben dem Quellcode auch lokale Entwicklungs- und Laufzeitdaten. Dazu gehörten virtuelle Python-Umgebungen, PlatformIO-Builds, SQLite-Datenbanken, Cache-Dateien, lokale Konfiguration und der interne `.git`-Ordner. Dadurch war das Paket rund 789 MB groß und ließ sich wegen einer geöffneten SQLite-Datenbank teilweise nicht zuverlässig archivieren.

## Durchgeführte Änderungen

- lokale und sensible Laufzeitdaten aus dem auslieferbaren Quellcode entfernt
- zentrale `.gitignore` für Python, PlatformIO, Audio, CSV, ZIP, Datenbanken, Modelle, Exporte und Logs erweitert
- Startseiten-README vollständig neu aufgebaut
- EventMonitorAI, Backend, Edge, Firmware und AudioLab verständlich eingeordnet
- Installationsanleitung für Backend und AudioLab ergänzt
- Coding Guidelines und Contribution-Prozess angelegt
- Security Policy und Datenschutz-/Datenhaltungsdokumentation ergänzt
- Branching-, Versionierungs- und Release-Regeln dokumentiert
- GitHub Actions für CI und Releases angelegt
- Dependabot, Issue-Vorlagen und Pull-Request-Vorlage ergänzt
- lokale Syntax- und Repository-Hygieneprüfung angelegt
- erste automatisierte Tests ergänzt
- Projektbenennung im Backend von NoiseMonitorAI auf EventMonitorAI vereinheitlicht
- Roadmap in nachvollziehbare Entwicklungsphasen gegliedert

## Bewusst nicht enthalten

- `.git`-Historie
- Python-Umgebungen (`venv`, `.venv`)
- PlatformIO-Buildverzeichnis `.pio`
- SQLite-Datenbanken
- `.env` mit lokalen Einstellungen
- Audio- und CSV-Messdaten
- lokale VS-Code-Konfiguration

Diese Inhalte dürfen nicht zurück in das Repository kopiert werden. Bestehende lokale Messdaten sollten separat gesichert werden.

## Prüfung

```text
python scripts/check_project.py
Projektprüfung erfolgreich.

pytest -q
2 passed
```

## Empfohlene Übernahme

Den Inhalt dieses Pakets in den lokalen Repository-Ordner kopieren. Die lokale `.git`-Historie des vorhandenen Repositorys bleibt dabei erhalten, sofern nur die Dateien und Ordner innerhalb des Paketwurzelverzeichnisses übernommen werden und der lokale `.git`-Ordner nicht gelöscht wird.

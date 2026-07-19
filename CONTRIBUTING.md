# Contributing to EventMonitorAI

Danke für dein Interesse an EventMonitorAI. Das Projekt befindet sich im aktiven Aufbau; kleine, nachvollziehbare Änderungen sind ausdrücklich erwünscht.

## Entwicklungsablauf

1. Issue oder Backlog-Eintrag prüfen bzw. anlegen.
2. Branch von `main` erstellen:

```bash
git checkout main
git pull
git checkout -b feature/kurze-beschreibung
```

3. Änderung mit Tests und Dokumentation umsetzen.
4. Lokale Prüfung starten:

```bash
python scripts/check_project.py
```

5. Kleine, sprechende Commits erstellen.
6. Pull Request mit Ziel, Änderung, Testnachweis und möglichen Risiken öffnen.

## Pull-Request-Anforderungen

- keine privaten Audio-, CSV-, Datenbank- oder `.env`-Dateien
- Python-Code kompiliert ohne Syntaxfehler
- vorhandene Tests sind erfolgreich
- neue Logik ist soweit sinnvoll getestet
- öffentliche Schnittstellen und Konfigurationen sind dokumentiert
- `CHANGELOG.md` wird bei benutzerrelevanten Änderungen ergänzt

## Commit-Konvention

Empfohlene Präfixe:

- `feat:` neue Funktion
- `fix:` Fehlerkorrektur
- `docs:` Dokumentation
- `refactor:` interne Umstrukturierung
- `test:` Tests
- `build:` Build- oder Abhängigkeitsänderung
- `ci:` CI-Konfiguration
- `chore:` Wartung

Beispiel:

```text
feat(audio-lab): add duplicate-safe folder import
```

Weitere Regeln: [docs/development/CODING_GUIDELINES.md](docs/development/CODING_GUIDELINES.md)

# Branching und Releases

## Branches

- `main`: jederzeit nachvollziehbarer Integrationsstand
- `feature/<name>`: neue Funktionen
- `fix/<name>`: Fehlerkorrekturen
- `docs/<name>`: reine Dokumentationsänderungen
- `release/<version>`: optional zur Stabilisierung größerer Releases

Direkte Entwicklungscommits auf `main` sollten vermieden werden.

## Versionierung

Das Projekt verwendet Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

Während der Alpha-Phase ist `0.x.y` vorgesehen. Vorabversionen können beispielsweise so benannt werden:

```text
v0.2.0-alpha.1
```

## Release-Ablauf

1. Roadmap-Ziel und offene Blocker prüfen.
2. Versionen in Anwendung und Dokumentation abgleichen.
3. Tests und Projektprüfung ausführen.
4. `CHANGELOG.md` unter einer festen Version aktualisieren.
5. signierten oder annotierten Tag erstellen.
6. GitHub Release aus dem Tag erzeugen.
7. Quellcodepaket und relevante Prüfsummen veröffentlichen.

```bash
git tag -a v0.2.0-alpha.1 -m "EventMonitorAI v0.2.0-alpha.1"
git push origin v0.2.0-alpha.1
```

Runtime-Daten, Audioaufnahmen, Datenbanken und lokale Modelle gehören nicht in Release-Artefakte.

# Security Policy

## Unterstützte Versionen

Bis zum v1.0-Tag werden Sicherheitskorrekturen auf dem aktuellen Release-Kandidaten
und danach für die jeweils aktuelle Minor-Version bereitgestellt. Kritische
Korrekturen erhalten einen Patch-Release.

## Sicherheitslücken melden

Bitte veröffentliche vermutete Schwachstellen, Zugangsdaten oder personenbezogene Beispieldaten **nicht** in einem öffentlichen Issue. Melde sie über die private Security-Advisory-Funktion des GitHub-Repositorys oder direkt an den Repository-Verantwortlichen.

Eine Meldung sollte enthalten:

- betroffene Komponente und Version
- nachvollziehbare Reproduktionsschritte
- mögliche Auswirkungen
- falls möglich, einen Vorschlag zur Behebung

## Sensible Daten

Nicht committen:

- Audioaufnahmen und Messpakete
- SQLite-Datenbanken
- `.env`-Dateien
- WLAN-, API- oder Verschlüsselungsschlüssel
- reale Personen-, Adress- oder Standortdaten
- trainierte Modelle, wenn sie aus privaten Audiodaten abgeleitet wurden

Die zentrale `.gitignore` deckt diese Dateitypen ab. Vor jedem Push sollte dennoch `git status` kontrolliert werden.

Das aktuelle technische Review und verbleibende Betriebsauflagen stehen unter
[`docs/operations/SECURITY_PRIVACY_REVIEW.md`](docs/operations/SECURITY_PRIVACY_REVIEW.md).

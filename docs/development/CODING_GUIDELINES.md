# Coding Guidelines

## Allgemein

- Quellcode, Variablennamen und technische Bezeichner auf Englisch.
- Benutzeroberfläche und fachliche Dokumentation dürfen deutsch sein.
- Funktionen klein halten und eine klar erkennbare Aufgabe geben.
- Keine Zugangsdaten, privaten Pfade oder Messdaten hart codieren.
- Konfiguration über Umgebungsvariablen oder versionierte Beispieldateien.
- Fehler nicht kommentarlos verschlucken; Kontext protokollieren oder weitergeben.

## Python

- Python 3.11+ und Typannotationen für neue öffentliche Funktionen.
- PEP 8 als Grundlage; maximale Zeilenlänge 100 Zeichen.
- Importe in Standardbibliothek, Drittanbieter und lokale Pakete gruppieren.
- `pathlib.Path` statt manueller Pfadverkettung.
- Datenbankzugriffe über klar definierte Module und Transaktionen.
- Zeitstempel möglichst als ISO 8601 mit expliziter Zeitzone speichern.
- Modelle, Schemas und API-Logik trennen.

## API

- stabile, sprechende Ressourcenpfade verwenden.
- Ein- und Ausgabe durch Pydantic-Schemas validieren.
- passende HTTP-Statuscodes liefern.
- Änderungen an API-Verträgen dokumentieren.
- Health-Endpunkte dürfen keine sensiblen Interna offenlegen.

## Audio und Machine Learning

- Rohdaten, Modellvorhersage und menschliche Bestätigung getrennt speichern.
- Modellname, Version, Confidence und Feature-/Preprocessing-Version protokollieren.
- automatische Vorhersagen niemals stillschweigend als bestätigte Wahrheit behandeln.
- Trainings-, Validierungs- und Testdaten nach Aufnahme/Tag trennen, nicht zufällig über benachbarte Segmente mischen.
- Datenschutz und Datenminimierung vor Feature-Komfort priorisieren.

## Tests

Neue Kernlogik sollte mindestens einen Test für den Normalfall und relevante Fehlerfälle erhalten. Tests dürfen keine echten privaten Audio- oder Messdaten benötigen; kleine synthetische Fixtures verwenden.

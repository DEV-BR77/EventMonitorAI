# Golden-Dataset-Kandidatenanalyse

Stand: 16. September 2026

## Ergebnis

Aus dem produktiven PostgreSQL-/Clip-Bestand wurde ein kleiner, noch nicht
freigegebener Kandidatenexport erstellt. Es wurden keine Samples automatisch
als Golden Dataset übernommen und keine Benchmarkzahlen erzeugt.

Export: `golden-candidate-v1/manifest.csv` mit drei WAV-Dateien. Alle drei
Dateien stimmen mit dem im Manifest gespeicherten SHA-256 überein und sind
untereinander verschieden.

Die AudioLab-Regressionssuite wurde am 16. September 2026 mit
`python -m pytest -q tests/test_audio_lab_*.py` ausgeführt und bestand mit
`40 passed` und Exit-Code `0`. Dieses technische Test-Gate ersetzt weder reale
Evaluation-Samples noch fachlich geprüfte Ground Truth.

## Tatsächlich untersuchte Datenbanken

| Datenbank | Aufnahmen | Segmente | Predictions | Modelle |
|---|---:|---:|---:|---:|
| `data/eventmonitor.sqlite3` | 0 | 0 | 0 | 0 |
| produktive PostgreSQL-Datenbank | 590 manuell klassifizierte Clip-Ereignisse mit Audioverknüpfung | Kandidatenexport: 3 | 3 | nicht relevant |
| `backend/data/eventmonitorai.db` | keine AudioLab-Tabellen | keine | keine | keine |

Die lokale AudioLab-SQLite bleibt leer; die relevanten Produktionsdaten liegen
in PostgreSQL und im Clip-Volume. Der Export enthält die drei Klassen
`CONVERSATION`, `OTHER_NOISE` und `FIRECRACKER`, jeweils mit Support 1.
Die Ereignisse sind als `manual` markiert und haben Reviewer sowie Reviewzeitpunkt.

## Klasseninventar

Exportierte Klassen: `CONVERSATION` (1), `OTHER_NOISE` (1), `FIRECRACKER` (1).

Die in Taxonomie, Roadmap oder Beispielen genannten Klassen wurden bewusst
nicht als vorhandene Datenklassen gezählt. Ohne reale gelabelte Segmente wären
solche Zahlen und Klassenabdeckungen erfunden.

## Candidate-Auswahl und Provenienz

Es gibt aktuell keinen Golden-Kandidaten. Für kein Sample sind Segment-ID,
Recording-ID, Originalreferenz, Input-Hash, Ground-Truth-Herkunft, Reviewer,
Reviewzeitpunkt oder Trainingszugehörigkeit vorhanden.

## Leakage und Duplikate

Auf den leeren Datenbestand konnten keine Sample-, Recording- oder Hash-
Überschneidungen geprüft werden. Near-Duplicate-Risiken bleiben für spätere
reale Daten offen: benachbarte Segmente, gleiche Session, Aufnahmeverbünde und
Mehrfachimporte. SHA-256 der Originaldatei ist in der Foundation vorbereitet;
eine Near-Duplicate-Audioanalyse ist weiterhin nicht implementiert.

## Support-Gate

Alle drei Klassen liegen unterhalb des bestehenden Support-Hinweises von 5
Samples. `Golden v1` darf daher noch nicht eingefroren werden. Der Export ist
ein realer Kandidatenpool, aber noch kein belastbarer Benchmark.

## Konkrete Voraussetzungen

1. Pro Klasse weitere unabhängige reale Clips sammeln.
2. Ground Truth und Begründungen fachlich gegen die drei Kandidaten prüfen.
3. Modellartefakte und Trainingsmanifeste für den Overlap-Abgleich bereitstellen.
4. Recording-/Session-/Zeitnähe und Near-Duplicates prüfen.
5. Erst bei ausreichendem Support Golden v1 einfrieren.
6. Erst danach einen Candidate kontrolliert zusammenstellen und einfrieren.

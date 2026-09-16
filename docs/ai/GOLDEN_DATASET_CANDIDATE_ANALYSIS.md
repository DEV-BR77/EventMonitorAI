# Golden-Dataset-Kandidatenanalyse

Stand: 16. September 2026

## Ergebnis

Im untersuchten Repository-Arbeitsstand ist kein realer AudioLab-Datenbestand
vorhanden, aus dem ein Golden Dataset aufgebaut werden könnte. Es wurden keine
Samples automatisch übernommen und keine Benchmarkzahlen erzeugt.

## Tatsächlich untersuchte Datenbanken

| Datenbank | Aufnahmen | Segmente | Predictions | Modelle |
|---|---:|---:|---:|---:|
| `data/eventmonitor.sqlite3` | 0 | 0 | 0 | 0 |
| `backend/data/eventmonitorai.db` | keine AudioLab-Tabellen | keine | keine | keine |

Die AudioLab-Schemata und Foundation-Tabellen sind im Code vorhanden, aber die
Arbeitsdatenbank enthält noch keine `recordings`, `segments`, `predictions` oder
`model_registry`-Zeilen. Daher existiert keine reale Klasse mit belegtem
Support, keine menschlich bestätigte Ground Truth und keine Provenienz.

## Klasseninventar

Reale Klassen: keine bestimmbar.

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

Alle Klassen liegen außerhalb der Support-Kategorien, weil keine realen
Evaluation-Samples vorhanden sind. `Golden v1` darf daher nicht eingefroren
werden. Ein Candidate-Dataset ohne Samples wäre kein belastbarer Benchmark.

## Konkrete Voraussetzungen

1. Audioaufnahmen in der AudioLab-Datenbank importieren.
2. Segmente mit stabiler Recording- und Originalreferenz erzeugen.
3. Menschlich eindeutige Ground Truth mit Herkunft erfassen.
4. Bereits im Training verwendete Aufnahmen und Artefakte nachvollziehbar
   markieren.
5. Klassen-Support und schwierige Bedingungen prüfen.
6. Erst danach einen Candidate kontrolliert zusammenstellen und einfrieren.

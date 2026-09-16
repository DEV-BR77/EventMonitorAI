# Baseline-Blocker

Stand: 16. September 2026

## 3B-K-Prüfung

Der Folgeauftrag 3B-K wurde im Repository erneut geprüft. Die AudioLab-
Regressionssuite ist weiterhin technisch bestanden (`40 passed`, Exit-Code `0`),
aber der fachliche Daten-Gate bleibt blockiert. Unter `data` ist kein realer
Audioimport oder sonstiger verwertbarer Audiodatenbestand vorhanden; die
Datenbankzählungen bleiben bei null.

## Golden Dataset

Kein Baseline-Run wurde gestartet. Der reale AudioLab-Datenbestand ist leer:

- `data/eventmonitor.sqlite3`: 0 Recordings, 0 Segmente, 0 Predictions, 0 Modelle;
- `backend/data/eventmonitorai.db`: keine AudioLab-Tabellen.

Ein separater Export aus der produktiven PostgreSQL-/Clip-Umgebung enthält
inzwischen 3 reale Kandidaten mit drei unterschiedlichen, hashgeprüften WAV-
Dateien. Er ist noch nicht Golden v1: Die Klassen haben jeweils nur Support 1
und der Training-Overlap ist noch nicht anhand von Modellmanifesten geprüft.

Damit fehlen unabhängige Samples, Ground Truth, Klassen-Support, Provenienz,
Input-Hashes und ein Trainingsmanifest. `Golden v1` kann nicht eingefroren
werden, ohne einen unzulässigen künstlichen Benchmark zu erzeugen.

## Test-Gate

Status: `passed` für den AudioLab-Regressions-Testlauf.

Am 16. September 2026 wurde reproduzierbar ausgeführt:

```text
python -m pytest -q tests/test_audio_lab_*.py
```

Ergebnis: `40 passed`, Exit-Code `0`. Die zuvor dokumentierte SciPy-DLL-
Blockade ist für diesen Testlauf nicht mehr reproduzierbar. Der produktive
Baseline-Run bleibt unabhängig davon wegen des leeren Datenbestands blockiert.

## Nicht ausgeführt

- kein Golden-v1-Freeze;
- kein Baseline-Evaluation-Run;
- keine Benchmarkzahlen;
- keine Modellaktivierung, Threshold- oder Produktionsänderung;
- keine alternativen Modelle und kein Shadow Processing.

## Voraussetzungen für Fortsetzung

1. Realen AudioLab-Datenbestand bereitstellen.
2. Ground Truth und Provenienz menschlich prüfen.
3. Training-Overlap und Recording-/Hash-Identität prüfen.
4. Candidate-Dataset erst nach erfüllten Gates einfrieren.
5. AudioLab-Test-Gate in einer zulässigen Umgebung als `passed` dokumentieren.
6. Danach ausschließlich `eventmonitor.evaluation.evaluate_model()` für den
   Baseline-Run verwenden.

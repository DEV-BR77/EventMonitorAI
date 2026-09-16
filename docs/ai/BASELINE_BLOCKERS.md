# Baseline-Blocker

Stand: 16. September 2026

## Golden Dataset

Kein Baseline-Run wurde gestartet. Der reale AudioLab-Datenbestand ist leer:

- `data/eventmonitor.sqlite3`: 0 Recordings, 0 Segmente, 0 Predictions, 0 Modelle;
- `backend/data/eventmonitorai.db`: keine AudioLab-Tabellen.

Damit fehlen unabhängige Samples, Ground Truth, Klassen-Support, Provenienz,
Input-Hashes und ein Trainingsmanifest. `Golden v1` kann nicht eingefroren
werden, ohne einen unzulässigen künstlichen Benchmark zu erzeugen.

## Test-Gate

Status: `blocked`.

Der relevante AudioLab-Testlauf wurde versucht. Die lokale Python-Umgebung
scheitert bereits beim Import von scikit-learn/SciPy mit einer durch die
Windows-Anwendungssteuerungsrichtlinie blockierten SciPy-DLL (`_lbfgsb` bzw.
`_ellip_harm_2`). Es wurde keine Sicherheitsrichtlinie umgangen.

Die korrekte Fortsetzung ist eine bereits vorgesehene Container- oder CI-
Umgebung beziehungsweise eine administrative Klärung von Installation,
Architektur/ABI und Policy. Der Status ist nicht `passed`.

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

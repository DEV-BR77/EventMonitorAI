# Arbeitsauftrag 3B-F – Datenbasis und Test-Gate freigeben

## Zweck

Die für Auftrag 3B fehlenden Voraussetzungen herstellen, ohne einen
künstlichen Golden-Datensatz oder erfundene Benchmarkzahlen zu erzeugen.
Auftrag 4 darf erst nach erfolgreicher Abnahme dieses Folgeauftrags beginnen.

## Ausgangslage

Die Prüfung vom 16. September 2026 ergab:

- `data/eventmonitor.sqlite3` enthält 0 Recordings, Segmente, Predictions und Modelle.
- `backend/data/eventmonitorai.db` enthält keine AudioLab-Tabellen.
- Es gibt daher keine bestätigte Ground Truth, Provenienz, Klassenabdeckung,
  Hashes oder Trainingsmanifeste für einen unabhängigen Golden-Datensatz.
- Der relevante Testlauf ist durch eine Windows-Anwendungssteuerungsrichtlinie
  blockiert, die SciPy-DLLs beim Import verhindert.

Belege: `docs/ai/BASELINE_BLOCKERS.md`,
`docs/ai/GOLDEN_DATASET_CANDIDATE_ANALYSIS.md` und
`docs/ai/GOLDEN_DATASET_GAPS.md`.

## Arbeitsumfang

### 1. Zulässige Testumgebung herstellen

- Den AudioLab-Testlauf in der vorgesehenen Container- oder CI-Umgebung
  ausführbar machen oder die SciPy-Installation/ABI/Policy administrativ
  klären.
- Keine Sicherheitsrichtlinie umgehen und keine DLL manuell aus unsicheren
  Quellen nachladen.
- Den exakten reproduzierbaren Testbefehl und die Umgebung dokumentieren.
- Das AudioLab-Test-Gate nur bei tatsächlich erfolgreichem Lauf als `passed`
  dokumentieren; bei Fehlschlag einen aktualisierten Blockerbericht schreiben.

### 2. Reale AudioLab-Daten bereitstellen

- Einen vorhandenen realen AudioLab-Datenbestand importieren oder den Nutzer
  ausdrücklich auffordern, ihn an einem nachvollziehbaren lokalen Pfad
  bereitzustellen.
- Keine synthetischen, Demo- oder automatisch angenommenen Samples als Golden
  Dataset verwenden.
- Recording-, Segment- und Originalreferenzen erhalten und Importprovenienz
  dokumentieren.

### 3. Ground Truth und Leakage-Prüfung vorbereiten

- Menschliche Bestätigung, Unsicherheit und ungelöste Fälle erfassen.
- Klasseninventar und Support aus den tatsächlichen Samples ableiten.
- Input-Hashes, Recording-/Session-Bezug, Near-Duplicate-Risiken und mögliche
  Trainingsüberschneidungen prüfen.
- Modellartefakte und Trainingsmanifest einbeziehen, sobald sie vorhanden sind.

### 4. Ergebnisberichte aktualisieren

Aktualisieren oder erzeugen:

- `docs/ai/GOLDEN_DATASET_CANDIDATE_ANALYSIS.md`
- `docs/ai/GOLDEN_DATASET_GAPS.md`
- `docs/ai/BASELINE_BLOCKERS.md` oder bei vollständiger Freigabe
  `docs/ai/GOLDEN_BASELINE_RESULT.md`

Bei erfüllten Gates zusätzlich den Candidate-Datensatz kontrolliert einfrieren
und ausschließlich `eventmonitor.evaluation.evaluate_model()` für den
Baseline-Run verwenden. Threshold-, Modell- oder Produktionsänderungen sind
weiterhin nicht Bestandteil dieses Auftrags.

## Abnahmekriterien / Gates

Alle folgenden Punkte müssen belegt sein:

1. AudioLab-Test-Gate ist in einer zulässigen Umgebung `passed`.
2. Es existieren reale, nachvollziehbar importierte Samples und Segmente.
3. Ground Truth ist menschlich geprüft und Unsicherheiten sind markiert.
4. Jede verwendete Klasse erfüllt den dokumentierten Support-Gate oder wird
   ausdrücklich als nicht ausreichend unterstützt ausgeschlossen.
5. Provenienz, Input-Hashes, Recording-/Session-Bezug und Trainings-Overlap
   sind geprüft; unbekannte Zustände gelten nicht als unabhängig.
6. Golden v1 ist reproduzierbar eingefroren.
7. Ein Baseline-Run liefert reproduzierbare Metriken, Confusion Matrix und
   Klassen-Support; alternativ bleibt der Auftrag mit konkreten Blockern offen.

## Nicht Bestandteil

- Candidate-Model-Recherche oder Modellauswahl (Auftrag 4).
- Adapter-Training, Shadow Evaluation, Threshold-/Calibration-Entscheidungen.
- Produktionsaktivierung oder Änderungen an Live-Klassifizierung.

## Abschlussbericht

Der Abschlussbericht muss den Status `passed` oder `blocked` tragen, alle Gates
mit Belegen referenzieren und klar benennen, ob Auftrag 4 gestartet werden darf.

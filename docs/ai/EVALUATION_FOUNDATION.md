# Evaluation Foundation

## Zweck und Grenzen

Die Evaluation Foundation ermöglicht reproduzierbare, produktionsgetrennte
Bewertungen des lokalen AudioLab-Modells. Sie verändert keine produktive
Klassifikation, Thresholds, Lernregeln oder Modellaktivierung. Alternative
Modelle, Shadow Processing, Promotion und ein großes Dashboard sind nicht Teil
dieser Foundation.

## Datenmodell

Die AudioLab-SQLite-Datenbank enthält zusätzlich:

- `evaluation_datasets`: Dataset-Key, Version, Beschreibung, Status,
  Frozen-Status, Manifest und Fingerprint;
- `evaluation_samples`: Segment-/Recording-Referenz, Input-Hash, getrennte
  Ground Truth, Status, Herkunft, Reviewer- und Notizfelder;
- `evaluation_runs`: Modell, Dataset, Versionen, Pipeline-Fingerprint,
  Laufstatus, Zählungen, Contamination-Status und Ergebnis-JSON;
- `evaluation_predictions`: eine Prediction je Run und Sample mit Klasse,
  Confidence, Inference-Zeit, Status und Fehlertext.

Als Sample-Identität wird die vorhandene Segment-ID verwendet. Der Input-Hash
ist SHA-256 über die vollständige Original-Audiodatei. Near-Duplicate-
Erkennung ist bewusst noch nicht Bestandteil der Foundation.

## Golden Dataset und Ground Truth

Datasets werden explizit erzeugt und erhalten fortlaufende Versionen. Samples
werden bewusst hinzugefügt; bestätigte, unsichere und ungelöste Ground Truth
werden unterschieden. Ein eingefrorenes Dataset kann weder still erweitert noch
verändert werden. Eine Änderung erfordert ein neues Dataset.

Ground Truth wird niemals aus einer Modellprediction abgeleitet. Unsichere und
ungelöste Samples werden im Run gespeichert, aber aus der eigentlichen
Benchmark-Metrik ausgeschlossen und als ausgeschlossen gezählt.

## Leakage Prevention

Beim Start eines Runs wird das Dataset auf Frozen-Status geprüft. Das
Modellartefakt wird geladen und sein gespeichertes Split-Manifest geprüft.
Golden-Samples kontaminieren den Run, wenn ihre Recording-ID im Trainingssplit
liegt. Sofern ein erweitertes Artefakt explizite Trainings-Segment-IDs oder
Input-Hashes enthält, werden diese ebenfalls geprüft. Kontaminierte Runs
erhalten den Status `contaminated` und dürfen nicht wie ein gültiger
Benchmark behandelt werden.

Die bestehende Aufnahme-basierte Train/Validation/Test-Aufteilung bleibt
erhalten und ist nicht mit einem langfristig eingefrorenen Golden Dataset
gleichzusetzen.

## Evaluation Runner

`eventmonitor.evaluation.evaluate_model()` lädt ein registriertes Joblib-
Artefakt, verarbeitet jedes bestätigte Sample mit dessen gespeicherter
Feature-Pipeline, speichert Einzelpredictions und erzeugt den Run-Status.
Fehler einzelner Samples werden isoliert gespeichert. Ein Lauf ohne gültige
Samples erzeugt keine scheinpräzisen Metriken.

## Metriken und Reports

Die Foundation berechnet Accuracy, Balanced Accuracy, Macro-, Weighted- und
Micro-Precision/Recall/F1, Per-Class-Report, Confusion Matrix und
Support-Warnungen. Die Matrixdaten bleiben strukturiert im Ergebnis-JSON.
Einzelpredictions ermöglichen später FP/FN-Listen, Disagreement und
anklickbare Sampleansichten. Threshold-Optimierung und Abstention werden noch
nicht produktiv angewendet.

## Bekannte Grenzen

Die vorhandene Modellregistrierung enthält noch keine vollständige Fine-Tune-
Abstammung oder Trainingssampleliste. Ohne unabhängig eingefrorene Samples
und belastbare Ground Truth wird kein Baseline-Run als Qualitätsnachweis
behauptet. Modellvergleich, Shadow Models, Kalibrierung, Threshold-Sweeps,
Near-Duplicate-Erkennung und große UI folgen erst nach der Foundation.

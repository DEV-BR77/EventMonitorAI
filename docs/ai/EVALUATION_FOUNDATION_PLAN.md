# Implementierungsplan: Evaluation Foundation

## Bestehende Struktur

Die Foundation erweitert die vorhandene AudioLab-SQLite-Struktur in
`tools/audio-lab/eventmonitor/db.py`. Wiederverwendet werden `recordings`,
`segments`, `predictions`, `model_registry`, die bestehende Feature-Pipeline,
`load_model()` und die vorhandene Metrikberechnung. Die bestehende
aufnahmebasierte Trainingsaufteilung bleibt unverändert.

## Neue Struktur

Ergänzt werden versionierte Evaluation-Datasets, Dataset-Samples und getrennte
Ground Truth, Evaluation Runs sowie Run-Predictions. Predictions bleiben von
Ground Truth getrennt. Reports werden aus gespeicherten Einzelpredictions
reproduzierbar erzeugt.

## Identität und Hash

Ein Evaluation-Sample referenziert ein vorhandenes Segment. Der Input-Hash ist
der SHA-256-Hash der vollständigen Original-Audiodatei (`recordings.audio_path`)
und wird zusammen mit Segment- und Recording-ID gespeichert. Damit werden
identische Dateiinputs und gemeinsame Ursprungsaufnahmen erkannt. Eine
Near-Duplicate-Audioanalyse ist ausdrücklich nicht Teil dieser Foundation.

## Leakage

Beim Run werden Sample-ID, Input-Hash und Recording-ID geprüft. Zusätzlich wird
das Split-Manifest des geladenen Modellartefakts ausgewertet: Ein Golden-Sample
mit einer Recording-ID im Trainingssplit kontaminiert den Run. Ein kontaminierter
Run erhält den Status `contaminated` und liefert keine normale Benchmark-
Gültigkeit.

## Migration und Sicherheit

Bestehende Tabellen und Daten bleiben kompatibel. Es erfolgt keine automatische
Übernahme aller bestätigten Samples und kein automatischer Trainingseinschluss.
Frozen-Datasets werden nur durch eine neue Version geändert. Bestehende
Produktivklassifikation, Lernregeln und Modellaktivierung bleiben unberührt.

## Bewusste Grenzen dieses Auftrags

Keine alternativen Modelle, Shadow-Verarbeitung, Threshold-Optimierung,
Promotion, Retraining oder große UI werden eingeführt. Ohne gültiges
unabhängiges Golden Dataset wird kein Baseline-Ergebnis künstlich erzeugt.

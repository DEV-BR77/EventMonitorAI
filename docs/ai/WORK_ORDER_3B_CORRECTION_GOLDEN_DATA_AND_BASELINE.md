# Arbeitsauftrag 3B-K – Golden Dataset und Baseline abschließen

## Status und Gate-Entscheidung

Arbeitsauftrag 3B ist **nicht abgenommen**. Auftrag 4 „Candidate Model Research &
Selection“ darf noch nicht beginnen.

Der technische AudioLab-Testlauf ist freigegeben: `python -m pytest -q
tests/test_audio_lab_*.py` ergab am 16. September 2026 `40 passed`, Exit-Code `0`.
Der zuvor dokumentierte SciPy-/Windows-DLL-Blocker ist für diesen Lauf nicht mehr
reproduzierbar.

Das fachliche Gate bleibt blockiert, weil im untersuchten Arbeitsstand keine realen
AudioLab-Daten vorhanden sind:

- `data/eventmonitor.sqlite3`: 0 Recordings, 0 Segmente, 0 Predictions, 0 Modelle;
- `backend/data/eventmonitorai.db`: keine AudioLab-Tabellen.

Damit existieren weder ein unabhängiger Golden-v1-Bestand noch Ground Truth,
Klassen-Support, Provenienz, Input-Hashes, Trainingsmanifest, Baseline-Metriken,
Confusion Matrix oder High-Confidence-Fehler. Es dürfen keine Benchmarkzahlen
erfunden oder synthetische/Demo-Samples als Golden Dataset verwendet werden.

## Ziel

Einen kleinen, realen, menschlich geprüften und vom Training unabhängigen
Golden-v1-Kandidaten bereitstellen, kontrolliert einfrieren und den reproduzierbaren
Baseline-Run ausschließlich über `eventmonitor.evaluation.evaluate_model()`
durchführen. Erst danach darf Auftrag 4 gestartet werden.

## Arbeitsumfang

### 1. Reale Daten bereitstellen und importieren

- Einen vorhandenen realen AudioLab-Datenbestand verwenden oder den Nutzer zur
  Bereitstellung eines nachvollziehbaren lokalen Pfads auffordern.
- Recording-, Segment- und Originalreferenzen beim Import erhalten.
- Importquelle, Importzeitpunkt, Datenbank/Version und alle Ausschlüsse dokumentieren.
- Keine synthetischen, Demo- oder automatisch angenommenen Samples aufnehmen.

### 2. Ground Truth und Klassen-Support

- Kandidaten fachlich durch einen Menschen prüfen und je Sample `confirmed`,
  `uncertain` oder `unresolved` erfassen.
- Ground-Truth-Klasse, Reviewer, Reviewzeitpunkt, Begründung und Originalreferenz
  dokumentieren.
- Klasseninventar und Support ausschließlich aus tatsächlich verwendeten Samples
  ableiten.
- Klassen unterhalb des vereinbarten Support-Gates ausdrücklich ausschließen und
  nicht künstlich ausbalancieren.
- Schwierige Fälle, negative Beispiele und bekannte Grenzfälle sichtbar markieren.

### 3. Unabhängigkeit, Leakage und Contamination

- Input-Hashes für alle verwendeten Originale und Samples erfassen.
- Recording-, Session-, Sequenz-, Geräte- und Standortbezüge prüfen, soweit vorhanden.
- Trainingseinschluss anhand der Modellartefakte und Trainingsmanifeste prüfen.
- Exakte Duplikate, Mehrfachimporte und zeitlich/inhaltlich nahe Duplikate bewerten;
  unbekannte Zustände dürfen nicht als `independent` gelten.
- Prüfregeln, Ergebnisse, Ausschlüsse und verbleibende Limitierungen im Bericht
  festhalten. Eine nicht vorhandene Near-Duplicate-Audioanalyse ist als Limitierung
  zu benennen, nicht stillschweigend als bestanden zu behandeln.

### 4. Golden v1 einfrieren

- Einen bewusst zusammengestellten Candidate-Datensatz mit stabiler Dataset-ID und
  Version anlegen.
- Manifest-Fingerprint und Sample-/Input-Hashes erzeugen.
- Freeze erst nach bestandenen Ground-Truth-, Support- und Unabhängigkeitsprüfungen.
- Jede spätere Änderung muss eine neue Dataset-Version erzeugen.

### 5. Baseline reproduzierbar ausführen

- Den exakten Befehl, Interpreter-/Abhängigkeitsumgebung, Modell-ID/-Version,
  Dataset-ID/-Version, Seed und Pipeline-Fingerprint dokumentieren.
- Ausschließlich `eventmonitor.evaluation.evaluate_model()` verwenden.
- Persistieren und berichten: Accuracy, Balanced Accuracy, Macro-/Weighted-/Micro-
  Precision/Recall/F1, Per-Class-Metriken, Support, Confusion Matrix, Confidence-
  Verteilungen sowie Prediction-Referenzen.
- False Positives, False Negatives und High-Confidence-Fehler als konkrete
  `sample_id`s mit Klasse, Vorhersage und Confidence ausweisen.
- Reproduzierbarkeit durch erneuten Lauf oder einen belastbaren Manifest-/Run-Nachweis
  belegen; Abweichungen erklären.

## Abnahmekriterien

Alle Kriterien müssen mit Dateien, IDs, Run-Ausgaben oder Tabellen belegt sein:

1. AudioLab-Regressionssuite: `passed` mit reproduzierbarem Befehl.
2. Reale, nachvollziehbar importierte Recordings und Segmente vorhanden.
3. Ground Truth menschlich geprüft; unsichere und ungelöste Fälle markiert.
4. Jede verwendete Klasse erfüllt das Support-Gate oder ist ausgeschlossen.
5. Provenienz, Input-Hashes, Recording-/Session-Bezug und Trainings-Overlap geprüft.
6. Golden v1 ist versioniert, manifestiert und reproduzierbar eingefroren.
7. Baseline-Run liefert Metriken, Confusion Matrix, Support und High-Confidence-
   Fehlerlisten; Ergebnisse sind reproduzierbar.

## Zu aktualisierende Berichte

- `docs/ai/GOLDEN_DATASET_CANDIDATE_ANALYSIS.md`
- `docs/ai/GOLDEN_DATASET_GAPS.md`
- `docs/ai/BASELINE_BLOCKERS.md` oder bei vollständiger Freigabe
  `docs/ai/GOLDEN_BASELINE_RESULT.md`

Der Abschlussbericht muss `passed` oder `blocked` tragen, jedes Gate referenzieren
und eindeutig sagen, ob Auftrag 4 gestartet werden darf.

## Nicht Bestandteil

- Keine alternativen Modelle installieren oder auswählen.
- Kein Adapter-Training, Shadow Processing, Threshold-/Kalibrierungsentscheid.
- Keine Production- oder Live-Klassifizierungsänderung.
- Keine automatische Übernahme ungeprüfter Daten ins Training.

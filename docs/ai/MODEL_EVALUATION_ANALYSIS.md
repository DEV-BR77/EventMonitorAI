# Analyse: belastbare Evaluation der KI-Modelle

Stand: 16. September 2026
Status: Analyse und Lösungsansätze; keine Implementierung und keine finale Roadmap.

## Ergebnis

Der Repository-Stand bietet eine brauchbare Grundlage für reproduzierbare Einzeltests des lokalen AudioLab-Modells. Eine belastbare Antwort auf die Frage, welches Modell unter welchen Bedingungen am zuverlässigsten erkennt, ist derzeit nicht möglich.

Belegt sind:
- lokales AudioLab-Modell als gewichtete scikit-learn-Logistic-Regression mit StandardScaler;
- 16 kHz, 5 Sekunden, Mono-Konvertierung, Resampling, Padding/Zuschnitt und Peak-Normalisierung;
- 140 Audiofeatures aus Log-Mel-Spektrum und Spektraldeskriptoren;
- Split auf Ebene vollständiger Ursprungsaufnahmen, standardmäßig 70/15/15;
- reproduzierbares Split-Manifest mit Seed, Recording-Zuordnung, Zählungen und Pipeline-Fingerprint;
- Accuracy, Balanced Accuracy, Macro-F1, klassenweise Precision/Recall/F1/Support und Confusion Matrix;
- Joblib-Artefakte und Modellregister mit Aktivierungshistorie und Rollback;
- menschliche Bewertung einzelner Modellvorschläge und Active-Learning-Scores.

Nicht belastbar belegt sind Produktionsmodell, Fine-Tune-Abstammung, Golden Set, gemeinsamer Test mehrerer Modelle, Shadow Models, Disagreement-Workspace, Threshold-Sweeps, Kalibrierung, Ressourcenmessung und Qualität nach Quelle oder Aufnahmebedingungen.

Die Aussagen „Fine-Tuning ist besser“, „höhere Confidence ist besser“ und „mehr Trainingsdaten verbessern das Modell“ sind daher aktuell nicht belastbar.

## Aktueller Modellsteckbrief

| Merkmal | Belegbarer Stand |
|---|---|
| Modell | lokale gewichtete Logistic Regression |
| Framework | scikit-learn; librosa/soundfile für Audio; joblib für Artefakte |
| Modellquelle | Projektcode; externe Basismodellquelle nicht belegt |
| Version | Artefaktversion 1.0.0 |
| Input | Mono- oder Stereo-Audioarray |
| Inputgröße | 16.000 Hz, 5,0 Sekunden |
| Preprocessing | Mono-Mix, soxr_hq-Resampling, mittiger Zuschnitt/zentriertes Padding, optionale Peak-Normalisierung |
| Features | 64 Log-Mel-Mittelwerte, 64 Log-Mel-Standardabweichungen und sechs Spektraldeskriptoren mit Mittelwert/Standardabweichung |
| Confidence | höchste predict_proba()-Wahrscheinlichkeit |
| Thresholds | kein Abstention- oder klassenweiser Threshold belegt |
| Format | Joblib |
| Hardware, Latenz, RAM | nicht belegt |

YAMNet wird in der Projektbeschreibung erwähnt, aber eine aktuell evaluierbare Version, ein Checkpoint und eine standardisierte Inference-Pipeline sind nicht belegt. ECAPA-TDNN dient der Stimmgruppierung und ist kein direkt vergleichbares Eventklassifikationsmodell.

## Datenaufteilung und Leakage

Die bestehende Aufteilung nach vollständiger Ursprungsaufnahme ist methodisch sinnvoll: Segmente derselben Aufnahme gelangen nicht gleichzeitig in Training und Test. Manifest, Seed und Feature-Fingerprint machen den Split reproduzierbar.

Nicht ausgeschlossen sind mehrere Dateien derselben realen Sequenz, Duplikate, nahezu identische Aufnahmen, zeitlich benachbarte Situationen sowie fehlende Source-, Sequenz-, Sensor- und Standortbeziehungen.

Lösungsansatz: zusätzlich source_id, session_id, Sequenz-ID, Geräte-/Standort-ID und Aufnahmeverbund erfassen. Hash-, Audiofingerprint- und Zeitfensterprüfungen vor dem Split durchführen. Das Golden Set vor Training einfrieren und per Manifest sowie Hash schützen. Änderungen erzeugen eine neue Set-Version.

## Golden Set und Ground Truth

Bestätigte Segmente sind als Trainingsbeispiele nutzbar, bilden aber noch kein Golden Evaluation Set. Jedes Evaluation-Sample benötigt sample_id, source_id, Zeitstempel, Ground-Truth-Klasse, Herkunft, Bewertungsstatus, relevante Metadaten und eine Originalreferenz, soweit zulässig. Unklar muss ein gültiger Ground-Truth-Status sein.

Lösungsansatz für spätere Datenstrukturen: evaluation_dataset mit Version und Frozen-Status; evaluation_sample mit Ground Truth und Schwierigkeit; Dataset-Mitgliedschaft mit Input-Hash; Audit für Trainingseinschluss. Training und Golden Set müssen maschinell auf Überschneidung geprüft werden.

Das Set sollte Standardfälle und bewusst schwierige Fälle enthalten: schlechte Bedingungen, Hintergrund, Überlagerung, geringe Lautstärke, Entfernung, Tageszeit, unterschiedliche Sensoren, ähnliche Klassen, Grenzfälle und bekannte Fehlklassifikationen. Diese Samples dürfen nicht automatisch ins Training fließen.

## Metriken und Confusion Matrix

Im Artefakt sind bereits klassenweise Metriken und eine Confusion Matrix vorhanden. Zentral fehlen jedoch False-Positive-/False-Negative-Samplelisten, Confidence-Verteilungen, gemeinsame Macro-/Weighted-/Micro-F1, Support-Warnungen, Metadatenaufschlüsselung, PR-Kurven und Konfidenzintervalle.

Lösungsansatz: Evaluation deterministisch aus Ground Truth und Predictions berechnen. Matrixzeilen sind Ground Truth, Spalten Prediction, ergänzt um None/Unknown. Jede Zelle referenziert sample_ids und öffnet deren Review. Accuracy bleibt Nebenmetrik.

Macro F1 gewichtet Klassen gleich, Weighted F1 nach Support und Micro F1 alle Entscheidungen gemeinsam. Kleine Testzahlen müssen sichtbar gewarnt werden.

## Modellvergleich

Das Modellregister kann mehrere Joblib-Artefakte aktivieren und zurückrollen, speichert aber noch keine gemeinsame Evaluation mehrerer Modelle auf identischen Samples.

Notwendige Prediction-Struktur: sample_id, model_id, model_version, predicted_class, confidence, inference_time, timestamp, raw_output_reference und evaluation_run_id. Der Modellsteckbrief muss Base Model, Fine-Tune-Elternversion, Dataset-Version, Klassen, Trainingstermin, Parameter, Checkpoints, Format, Lizenz und Deploymentstatus enthalten.

Production, Fine-Tune Current, Fine-Tune Previous und Candidate A/B sind derzeit keine nachweisbar standardisierten Vergleichsobjekte.

## Shadow Models und Disagreements

Ein produktionsentkoppelter Shadow-Pfad ist nicht belegt. Lösungsansatz: konfigurierbares Sampling nach Anteil, Zeitraum, Eventtyp, Quelle, Confidence oder Klasse; getrennte Queue und Evaluation Store; keine produktiven Alarme, Klassifikationen oder Lernregeln; begrenzte Parallelität und Ressourcenbudgets.

Der Disagreement-Workspace wird aus Predictions derselben sample_id gebildet. Sortierung: Confidence-Differenz, Klassenabweichung, Production gegen Fine-Tune, Anzahl abweichender Modelle, Eventtyp, Quelle und Zeitpunkt. Ground Truth muss Schreien, Sprache, anderes und unklar zulassen. Disagreement ist Review-Signal, keine automatische Trainingsfreigabe.

## Thresholds und Kalibrierung

predict_proba() ist nicht als kalibrierte Wahrscheinlichkeit nachgewiesen. Argmax ordnet jeden Input einer bekannten Klasse zu.

Lösungsansatz: Threshold-Sweeps 0,30 bis 0,90, klassenweise Precision-Recall-Kurven, Unknown/Abstain, Reliability Diagram, Brier Score oder ECE und versionierte Threshold-Konfiguration. Keine automatische Produktivsetzung des global besten Thresholds; Fachrisiken für False Positives und False Negatives berücksichtigen.

## Fine-Tuning und Governance

Ein reproduzierbares Basismodelltraining ist belegt. Ein vollständiger Fine-Tune-Verlauf mit Dataset-Versionen, Änderungen, Checkpoints und Vergleichsmessungen ist nicht belegt.

Lösungsansatz je Modellgeneration: Model-ID und Parent-ID, Dataset-Version und Sampleliste, Status Training/Offline Evaluation/Shadow Evaluation/Human Review/Candidate/Production, Parameter und Checkpoints, Golden-Set-Evaluation, Aktivierungsbegründung und Rollback. Jedes Trainingssample muss auditierbar einer Dataset-Version zugeordnet sein.

## Klassen und Architektur

Die Anwendung enthält allgemeine Audio-, Fein-, Kontext- und Personenklassen. Nicht belegt ist, dass sie akustisch ausreichend separierbar sind oder ein flaches Modell alle Aufgaben sinnvoll löst.

Zu prüfen sind Support, Verwechslungen, Maschinen-/Umwelt-Fehlalarme, Kontextklassen, Unknown/Other sowie hierarchische Klassifikation oder Router. Die Hypothese eines Routers für Human/Speech, Impact/Glass und General Audio darf erst nach Fehleranalyse entschieden werden.

## Alternativmodelle

Eine konkrete Kandidatenliste ist aus dem Repository allein nicht belastbar. Zu untersuchen sind General-Audio-Modelle wie YAMNet-Nachfolger, Audio-Transformer/AST-ähnliche Modelle, spezialisierte Speech-/Scream- und Impact-/Glass-Modelle, ECAPA für Sprecher, ONNX-/quantisierte Varianten sowie – nur bei vorhandenen Bilddaten – Vision- und multimodale Modelle.

Für jeden Kandidaten müssen Version, Architektur, Lizenz, kommerzielle Nutzung, Größe, CPU/GPU, Input, Klassen, Fine-Tuning, Latenz, RAM/VRAM, Offline-Betrieb, Datenschutz, Integrationsaufwand, Export, ONNX, Quantisierung und Wartungszustand verifiziert werden. Benchmarks allein reichen nicht. Zwei bis vier Shadow-Kandidaten sind erst nach Golden Set, Hardware- und Lizenzklärung belastbar auswählbar.

## Performance

CPU, GPU, RAM, VRAM, Modellgröße, Durchsatz, Inference-Zeit und externe API-Kosten/Latenz sind nicht belegt. Lösungsansatz: diese Werte je Modell, Hardware, Batch und Quantisierung erfassen und getrennt für produktive und Shadow-Pipeline ausweisen.

## Antworten auf die Kernfragen

| Frage | Ergebnis |
|---|---|
| Fine-Tuning besser? | Derzeit nicht belastbar bestimmbar. |
| Klassen besser/schlechter? | Kein versionsübergreifender Per-Class-Vergleich belegt. |
| Größte Fehlerklassen? | Derzeit nicht belastbar bestimmbar. |
| Klassen ausreichend unterscheidbar? | Derzeit nicht belastbar bestimmbar. |
| Ein Modell für alle Eventtypen? | Nicht belegt; Fehlerstruktur muss entscheiden. |
| Alternativmodelle? | Untersuchungskategorien vorhanden, aktuelle Lizenz-/Benchmarks fehlen. |
| Fehlende Daten? | Golden Set, Ground Truth, Source-/Sequenz-Metadaten, Modell-/Dataset-Abstammung, gemeinsame Predictions und Performance-Messungen. |

## Schlussfolgerung

Der stärkste vorhandene Baustein ist die aufnahmebasierte, reproduzierbare Aufteilung. Der größte Engpass ist die fehlende Governance eines unabhängigen, versionierten Testbestands. Ohne ihn sind Aussagen über Modellverbesserung, Klassenregressionen, Thresholds und Alternativmodelle ausdrücklich derzeit nicht belastbar bestimmbar.

Die spätere Umsetzung muss deshalb datenabhängig aufgebaut werden: erst unabhängige Samples und Ground Truth sichern, dann gemeinsame Predictions und Metriken, danach Shadow-/Review-Funktionen und erst anschließend Kandidaten, Kalibrierung und Produktivbedingungen. Dies ist eine fachliche Abhängigkeit, keine finale Roadmap.

# Lücken für Golden Dataset v1

Golden Dataset v1 ist derzeit blockiert.

| Bereich | Befund | Erforderliche Maßnahme |
|---|---|---|
| Samples | 3 reale Clip-Kandidaten exportiert | weitere unabhängige Samples je Klasse sammeln |
| Ground Truth | 3 manuell klassifizierte Kandidaten, erneute Golden-Review erforderlich | Reviewstatus und Begründung bestätigen |
| Provenienz | Ereignis-, Geräte-, Trigger- und Reviewdaten im Manifest vorhanden | Original-/Session-/Aufnahmeverbund ergänzen |
| Klassen | CONVERSATION, OTHER_NOISE, FIRECRACKER; je 1 Sample | reale Klassenbreite erweitern |
| Training-Overlap | nicht prüfbar, da kein Modell/Manifest und keine Samples vorhanden | Modellartefakte und Trainingsmanifeste bereitstellen |
| Input-Hashes | keine Hashes vorhanden | Candidate-Samples hashen |
| Near Duplicates | nicht prüfbar | mindestens Recording-/Session-/Zeitbezug prüfen; Audio-Near-Duplicate bleibt Limitierung |
| Support | je Klasse 1, unter Support-Hinweis 5 | keine künstliche Balance; weitere reale Samples sammeln |
| Dataset-Freeze | technisch vorhanden, fachlich nicht freigabefähig | erst nach erfüllten Gates einfrieren |
| Test-Gate | AudioLab-Regressionssuite bestanden (`40 passed`, Exit-Code `0`) | für den Baseline-Run dieselbe reproduzierbare Umgebung verwenden |

Unbekannte Zustände werden nicht als `independent` interpretiert.

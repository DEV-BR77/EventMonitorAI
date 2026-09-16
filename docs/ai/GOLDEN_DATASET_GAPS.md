# Lücken für Golden Dataset v1

Golden Dataset v1 ist derzeit blockiert.

| Bereich | Befund | Erforderliche Maßnahme |
|---|---|---|
| Samples | 0 reale Aufnahmen/Segmente | AudioLab-Datenbestand bereitstellen |
| Ground Truth | keine bestätigten, unsicheren oder ungelösten Samples vorhanden | fachliche Review erfassen |
| Provenienz | keine Recording-, Source-, Session- oder Reviewer-Daten vorhanden | Original- und Reviewreferenzen erhalten |
| Klassen | keine reale Klassenverteilung bestimmbar | Klassen aus tatsächlichen Samples ableiten |
| Training-Overlap | nicht prüfbar, da kein Modell/Manifest und keine Samples vorhanden | Modellartefakte und Trainingsmanifeste bereitstellen |
| Input-Hashes | keine Hashes vorhanden | Candidate-Samples hashen |
| Near Duplicates | nicht prüfbar | mindestens Recording-/Session-/Zeitbezug prüfen; Audio-Near-Duplicate bleibt Limitierung |
| Support | für alle Klassen 0 | keine künstliche Balance; unabhängige Samples sammeln |
| Dataset-Freeze | technisch vorhanden, fachlich nicht freigabefähig | erst nach erfüllten Gates einfrieren |
| Test-Gate | blockiert durch SciPy-DLL-Policy | vorgesehene Container-/CI-Umgebung verwenden oder Policyursache administrativ klären |

Unbekannte Zustände werden nicht als `independent` interpretiert.

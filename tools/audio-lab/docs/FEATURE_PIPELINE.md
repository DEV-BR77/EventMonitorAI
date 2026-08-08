# Versionierte Feature- und Preprocessing-Pipeline

AudioLab bindet jedes trainierte Modell an eine vollständige, unveränderliche
Vorverarbeitungskonfiguration. Die aktuelle Pipeline-Version ist `1.0.0`.

## Verarbeitung

1. Stereo- oder Mehrkanalaudio wird zu Mono gemittelt.
2. Nicht-endliche Werte werden bereinigt.
3. Das Signal wird hochwertig auf 16 kHz resampelt.
4. Lange Segmente werden mittig auf fünf Sekunden zugeschnitten, kurze Segmente
   symmetrisch mit Stille aufgefüllt.
5. Das Signal wird spitzenwertnormalisiert.
6. Berechnet werden Mittelwert und Standardabweichung von 64 Log-Mel-Bändern
   sowie ZCR, RMS, Spektralzentrum, Bandbreite, Rolloff und Flachheit.

Das Ergebnis besitzt 140 stabil benannte Werte. Die kanonische JSON-Konfiguration
erhält einen SHA-256-Fingerprint. Modellartefakte müssen Pipeline-Version,
Fingerprint und die geordnete Merkmalsnamensliste speichern. Eine abweichende
Konfiguration ist dadurch keine stillschweigende Änderung, sondern eine neue,
überprüfbare Pipeline-Identität.

Die Implementierung befindet sich in `eventmonitor/features.py`. Änderungen am
mathematischen Verhalten erfordern eine neue `FEATURE_PIPELINE_VERSION` und
Kompatibilitätstests für bereits gespeicherte Modellartefakte.

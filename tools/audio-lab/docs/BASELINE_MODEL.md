# Basismodell und Qualitätsmetriken

Das erste lokale Basismodell ist eine gewichtete logistische Regression auf den
versionierten Audiofeatures. Ein `StandardScaler` wird ausschließlich mit dem
Trainingssplit angepasst. Das Modell sieht weder Validierungs- noch Testaufnahme
während des Trainings.

Für Validierung und den bis zur Abschlussmessung unberührten Test werden
dokumentiert:

- Accuracy
- Balanced Accuracy
- Macro-F1
- Precision, Recall, F1 und Support je Klasse
- Konfusionsmatrix mit stabiler Klassenreihenfolge

Das lokale Joblib-Artefakt enthält Modellversion, Erstellungszeitpunkt,
Feature-Konfiguration und -Fingerprint, geordnete Merkmalsnamen, Klassenliste,
vollständiges Split-Manifest und sämtliche Metriken. Beim Laden werden
Artefaktversion und Pipeline-Fingerprint geprüft.

Das Training ist im AudioLab unter **Modelltraining** verfügbar. Es benötigt
mindestens zwei bestätigte Klassen und drei unabhängige Ursprungsaufnahmen.

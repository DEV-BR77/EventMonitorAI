# Lokale Modellverwaltung und Rollback

Jedes trainierte Joblib-Artefakt wird im lokalen Modellregister erfasst. Das
Register speichert Name und Pfad, Artefaktversion, Pipeline-Fingerprint,
Qualitätsmetriken, Status und Aktivierungszeitpunkt. Vor jeder Aktivierung wird das
Artefakt vollständig geladen und gegen seine Version und Pipeline geprüft.

Es gibt immer höchstens ein aktives Modell. Eine Aktivierung schreibt zusätzlich
einen unveränderlichen Historieneintrag mit Grund und Zeitpunkt. **Auf vorheriges
Modell zurückrollen** sucht die letzte andere, nicht archivierte Aktivierung,
prüft deren Datei erneut und schaltet sie atomar aktiv. Das aktive Modell kann
nicht archiviert werden.

Die Verwaltung befindet sich unter **Modelltraining**. Modellvorschläge und
Embeddings verwenden standardmäßig die aktive Version; für kontrollierte
Vergleiche kann weiterhin explizit eine andere lokale Version ausgewählt werden.

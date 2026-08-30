# Bildnachweise und PDF-Dokumentation

EventMonitorAI verwendet ein bewusst kleines, integriertes Dokumentationsmodul statt
eines zusätzlichen CMS. Dadurch gelten Anmeldung, Rollen und Tenant-Isolation des
Dashboards ohne eine zweite Benutzerverwaltung auch für Bilder und Schriftstücke.

## Bereiche

Unter **Beta → Bildnachweise** können angemeldete Benutzer JPEG-, PNG- und WebP-Dateien
bis 15 MB mit Titel, frei pflegbarer Kategorie und Aufnahmezeitpunkt anlegen. Die Ansicht
zeigt die neuesten Nachweise zuerst und lässt sich nach Kategorie sowie Von-/Bis-Datum
filtern.

Unter **Beta → Dokumente & Vorlagen** werden PDF-Dateien bis 25 MB nach demselben Prinzip
verwaltet. Damit können später Vorlagen, ausgefüllte Schriftstücke, Lärmprotokolle und
sonstige Anlagen unterschieden werden. Administratoren dürfen Einträge löschen.

## Sicherheit und Datentrennung

- Der Server prüft MIME-Typ und Dateisignatur; SVG, HTML und ausführbare Formate werden
  nicht angenommen.
- Dateinamen bestimmen niemals den Speicherpfad. Intern werden zufällige Dateinamen in
  einem Verzeichnis je Kundenbereich verwendet.
- Metadaten tragen `tenant_id`; die zentrale SQLAlchemy-Isolation begrenzt Listen-,
  Datei- und Löschzugriffe auf den angemeldeten Kundenbereich.
- Dateien werden nur über authentifizierte API-Endpunkte ausgeliefert.
- Uploads speichern den ursprünglichen Dateinamen, Zeitpunkt, Größe und Benutzer zur
  Nachvollziehbarkeit.

## Sicherung und Weiterentwicklung

Das Docker-Volume `eventmonitor_documentation_data` wird im automatischen und manuellen
Backup einschließlich Prüfsummen berücksichtigt und vom Restore-Skript wiederhergestellt.
Originalereignisse und Audiodaten bleiben davon getrennt.

Die integrierte Lösung ist die CMS-Grundlage. Spätere Ausbaustufen können Schlagwörter,
Ereignisverknüpfungen, Freigabe-Workflows, PDF-Erzeugung und eine redaktionelle
Übersichtsseite ergänzen, ohne Daten oder Benutzer in ein Fremdsystem migrieren zu müssen.

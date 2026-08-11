# Notizen, Bestätigungsstatus und Änderungshistorie

Cases besitzen einen frei bearbeitbaren Titel, ausführliche Notizen und einen der
Bestätigungsstatus **Entwurf**, **Bestätigt** oder **Abgelehnt**. Änderungen sind
nur zusammen mit einem Bearbeiternamen und einer Begründung speicherbar.

Jede Erstellung und Änderung erzeugt eine unveränderliche Revision mit:

- fortlaufender Revisionsnummer;
- Aktion, Bearbeiter, Begründung und UTC-Zeitpunkt;
- vollständigem Vorher-/Nachher-Zustand;
- Hash der vorherigen Revision;
- eigenem SHA-256-Hash über sämtliche Revisionsdaten.

SQLite-Trigger verhindern Updates und Löschungen an Revisionen. AudioLab prüft die
gesamte Hash-Kette beim Anzeigen und meldet ihren Integritätsstatus. Die Historie
ist damit lokal append-only und nachträgliche Manipulationen werden sichtbar. Für
eine rechtlich qualifizierte Langzeitarchivierung bleibt zusätzlich ein externes,
unveränderliches Sicherungsmedium erforderlich.

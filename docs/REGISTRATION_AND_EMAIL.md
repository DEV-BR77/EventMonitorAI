# Registrierung und E-Mail-Bestätigung

Die öffentliche Website verlinkt auf `https://dashboard.eventmonitor.eu/?register=1`.
Eine Registrierung normalisiert die E-Mail-Adresse, hasht das Passwort und erzeugt einen
eigenen, zunächst inaktiven Kundenbereich. Das Konto und seine Mitgliedschaft werden erst
nach Aufruf des einmaligen, SHA-256-gehasht gespeicherten und 24 Stunden gültigen Links
aktiviert. Der Link selbst wird nicht in der Datenbank gespeichert.

Der Plattformadministrator sieht neue Registrierungen oben im Dashboard am Glockensymbol.
Die Meldung unterscheidet zwischen noch offener und abgeschlossener E-Mail-Bestätigung und
kann als gelesen markiert werden. Normale Kundenadministratoren sehen ausschließlich
Benachrichtigungen ihres eigenen Mandanten.

## Resend-Konfiguration

Vor Aktivierung in Produktion müssen folgende Werte in `.env.docker` hinterlegt werden:

```text
PUBLIC_BASE_URL=https://dashboard.eventmonitor.eu
RESEND_API_KEY=<separater Resend-API-Schlüssel>
RESEND_FROM=EventMonitorAI <noreply@eventmonitor.eu>
RESEND_REPLY_TO=kontakt@eventmonitor.eu
```

Ohne `RESEND_API_KEY` und `RESEND_FROM` antwortet die Registrierung bewusst mit HTTP 503 und legt
kein halbfertiges Konto an. Geheimnisse gehören ausschließlich in `.env.docker` und niemals
ins Repository. `eventmonitor.eu` muss bei Resend für ausgehenden Versand verifiziert bleiben;
eingehende Nachrichten an `kontakt@eventmonitor.eu` werden bei IONOS weitergeleitet und die
IONOS-MX-Einträge dürfen nicht durch Resend-Inbound-Einträge ersetzt werden. Der API-Schlüssel
soll ausschließlich Versandberechtigung besitzen und bei Offenlegung sofort rotiert werden.

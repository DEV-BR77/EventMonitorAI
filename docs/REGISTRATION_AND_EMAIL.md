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

## SMTP-Konfiguration

Vor Aktivierung in Produktion müssen folgende Werte in `.env.docker` hinterlegt werden:

```text
PUBLIC_BASE_URL=https://dashboard.eventmonitor.eu
SMTP_HOST=<SMTP-Server>
SMTP_PORT=587
SMTP_USERNAME=<SMTP-Benutzer>
SMTP_PASSWORD=<SMTP-Passwort>
SMTP_FROM=<bestätigte Absenderadresse>
SMTP_STARTTLS=true
```

Ohne `SMTP_HOST` und `SMTP_FROM` antwortet die Registrierung bewusst mit HTTP 503 und legt
kein halbfertiges Konto an. Geheimnisse gehören ausschließlich in `.env.docker` und niemals
ins Repository. Für die produktive Freischaltung sind eine bestätigte Absenderadresse und
gültige SMTP-Zugangsdaten erforderlich.

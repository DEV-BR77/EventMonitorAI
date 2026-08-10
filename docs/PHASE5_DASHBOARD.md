# Dashboard und Integrationen

Das Dashboard wird vom FastAPI-Backend unter `http://127.0.0.1:8000/` ausgeliefert. Beim
ersten Aufruf wird über **Ersten Admin anlegen** ein lokales Administratorkonto erzeugt.
Danach ist diese Funktion automatisch gesperrt.

## Rollen

- `viewer`: Dashboard, Ereignisse und Auswertungen lesen
- `operator`: zusätzlich Geräte und Benachrichtigungsregeln verwalten
- `admin`: zusätzlich Benutzerkonten anlegen

Sitzungstoken werden mit `AUTH_SECRET` signiert. Vor einem Betrieb außerhalb des lokalen
Entwicklungsrechners muss dieser Wert durch ein langes, zufälliges Geheimnis ersetzt werden.
TLS wird für Zugriffe über ein Netzwerk vorausgesetzt.

## Live-Ansicht und Auswertungen

`/ws/events` liefert neue Ereignisse unmittelbar an angemeldete Clients. Kalender,
Timeline, Kategorien, Kennzahlen und die Wochentag/Stunden-Heatmap können nach Zeitraum
und Gerät gefiltert werden. Die REST-Routen liegen unter `/api`.

Die zentrale Zeitraumwahl gilt einheitlich für Timeline, Heatmap, Kalender und Kennzahlen.
Einzelne Tage sowie Von-bis-Zeiträume werden über Kalenderfelder gewählt; im Kalender
erscheint jeder Tag des ausgewählten Zeitraums. Der Live-Ereignisstrom blendet bearbeitete
und automatisch gelernte Ereignisse standardmäßig aus. Sie können über
**Bearbeitete anzeigen** zur Kontrolle und Korrektur wieder eingeblendet werden.
Noch nicht gespeicherte Kategorie- und Feinzuordnungen im Live-Ereignisstrom bleiben
bei einer Aktualisierung der Liste erhalten, damit mehrere Ereignisse nacheinander
vorbereitet und schnell bestätigt werden können.

Im KI-Klassenkatalog bilden Basisklassen die Hauptkategorien und Feinzuordnungen deren
Unterarten. `Aktiv` steuert die Verfügbarkeit in Auswahlfeldern, `Trainierbar` die
Verwendung bestätigter Beispiele für das Modelltraining und `Ausblenden` die
standardmäßige Sichtbarkeit automatisch erkannter Treffer. Zughupen werden als
trainierbare Feinzuordnung `TRAIN_HORN` unter der Basisklasse `HORN` geführt.

## Home Assistant

In Home Assistant kann eine Webhook-Automation angelegt werden. Deren URL wird als
`HOME_ASSISTANT_WEBHOOK_URL` konfiguriert. Optional wird `HOME_ASSISTANT_TOKEN` als
Bearer-Token gesendet. Eine passende Dashboard-Regel filtert Kategorie, Gerät,
Konfidenz und Mindestpegel und schützt über einen Cooldown vor Alarmfluten.

Der JSON-Body enthält:

```json
{
  "event": "eventmonitorai_event",
  "rule": "Lautes Rufen",
  "data": {
    "id": 42,
    "timestamp": "2026-07-29T12:00:00+00:00",
    "category": "VOICE",
    "label": "Rufen",
    "confidence": 0.91,
    "db_level": 78.4,
    "device": "terrace"
  }
}
```

## PostgreSQL und mehrere Geräte

SQLite bleibt der lokale Standard. Für PostgreSQL:

```dotenv
DATABASE_URL=postgresql+psycopg://eventmonitor:password@localhost/eventmonitor
```

Neue Geräte werden beim ersten eingehenden Ereignis automatisch registriert und erhalten
einen `last_seen`-Zeitstempel. Anzeigen und Regeln können je Geräte-ID gefiltert werden.
Für produktive Upgrades sollte im nächsten Schritt Alembic als explizites
Migrationswerkzeug ergänzt werden.

# Security- und Datenschutzreview

Stand: 9. August 2026. Umfang: Docker-Deployment, FastAPI, Dashboard,
PostgreSQL, Audio-Clips, Push, Live-WebSockets, Backup und Upgrade.

## Behobene Befunde

| Befund | Maßnahme |
|---|---|
| Ereignis-WebSocket akzeptierte Token gelöschter/deaktivierter Benutzer bis zum Ablauf | Benutzer und Aktivstatus werden bei jedem WebSocket-Aufbau gegen PostgreSQL geprüft. |
| Unbegrenzte Loginversuche | Acht Fehlversuche pro Benutzerkennung führen zu einer 15-minütigen Drosselung mit `Retry-After`. Erfolgreiche Anmeldung löscht den Zähler. |
| Unsichere Entwicklungsgeheimnisse könnten versehentlich mit PostgreSQL starten | Produktionsstart verlangt mindestens 32 Zeichen für `AUTH_SECRET` und 24 Zeichen für `INGEST_API_KEY`. |
| Veränderliche Python- und PostgreSQL-Versionen | Direkte Python-Abhängigkeiten und das PostgreSQL-Multiarch-Image sind reproduzierbar gepinnt. |
| Geschützte API-Antworten konnten zwischengespeichert werden | `/auth`, `/api`, `/events` und `/push` senden `Cache-Control: no-store`; Ressourcen sind `same-origin`. |
| Backups ohne definierte Integritäts- und Löschstrategie | Dumps und Cliparchive erhalten SHA-256-Prüfsummen, restriktive Umask und eine konfigurierbare 30-Tage-Aufbewahrung. |
| Als Fehlalarm bestätigte Audioereignisse blieben erhalten | „Kein Lärm / verwerfen“ löscht Ereignis und Clip; nur ein anonymes Label-Zählmuster bleibt zum Lernen. |

## Schutzmaßnahmen

- PBKDF2-SHA256 mit 600.000 Iterationen und individuellem 128-Bit-Salt
- HMAC-signierte, zeitlich begrenzte Zugriffstoken
- rollenbasierte Prüfung aus dem aktuellen Datenbankkonto, nicht aus der
  Rollenangabe des Tokens
- gesonderte Freigabe je Benutzer und Mikrofon für Live-Audio
- API-Schlüssel für Geräte-Ingest und signierte Push-Antworten
- CSP, HSTS hinter HTTPS, Frame-, MIME-, Referrer- und Permissions-Header
- Container läuft ohne Root; PostgreSQL und Clips liegen in getrennten Volumes
- `.env`, Audio, Datenbanken, Backups, Modelle und Exporte sind von Git ausgeschlossen

## Verbleibende Risiken und Betriebsauflagen

1. Zugriffstoken liegen wegen der statischen PWA im Browser-LocalStorage. Die
   strikte CSP reduziert XSS-Risiken, ersetzt aber keine HttpOnly-Cookie-
   Architektur. Deshalb keine fremden Skripte einbinden und Tokenlaufzeit kurz
   halten.
2. Port 8015 bindet derzeit für den lokalen Reverse-Proxy. Windows-Firewall und
   Router müssen direkten externen Zugriff sperren; öffentlich darf nur Caddy
   mit gültigem TLS-Zertifikat erreichbar sein.
3. Backups enthalten Konten und Audio. Der Ordner `backups/` benötigt lokale
   Zugriffsrechte und verschlüsselte Datenträgersicherung.
4. Akustische Ähnlichkeit ist keine Identitätsfeststellung. Personenprofile
   dürfen nur mit geklärter Rechtsgrundlage, minimaler Aufbewahrung und
   manueller Bestätigung verwendet werden.
5. Dieses Review ist ein technisches internes Review, kein externer
   Penetrationstest und keine Rechtsberatung.

## Datenschutz-Abnahme

- Dateninventar und Aussagegrenzen: [`PRIVACY_AND_DATA.md`](PRIVACY_AND_DATA.md)
- Backup/Löschung: [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md)
- Betreiber dokumentiert Zweck, Rechtsgrundlage, Empfänger, Aufbewahrung und
  Betroffenenrechte vor Freigabe weiterer Nachbarkonten.
- Reale Audio- oder Personendaten werden niemals als Testfixture, Issue-Anhang
  oder Git-Artefakt verwendet.

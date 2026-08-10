# Kundenbereiche, Abonnements und externe Mikrofone

Jeder Kundenbereich ist ein technisch getrennter Mandant. Ereignisse, Clips,
Mikrofone, Kalibrierungen, Personenprofile, Statistiken, Benachrichtigungen und
Lärmprotokolle tragen eine `tenant_id`. Die Datenbanksitzung ergänzt diese
Kennung bei neuen Datensätzen und filtert Lesezugriffe zentral. Auch
WebSocket-Ereignisse, Pushversand und nächtliche Prüfläufe werden je Mandant
ausgeführt.

Benutzerrechte und Abonnementstatus sind bewusst getrennt:

- Die Mitgliedschaft enthält die Rolle `viewer`, `operator` oder `admin` im
  jeweiligen Kundenbereich.
- Das Abonnement enthält Tarif, Status, Geräteobergrenze und Aufbewahrungszeit.
- `trialing` und `active` erlauben neue Geräte. Eine Zahlungsanbieter-Anbindung
  ist noch nicht aktiv; der Status wird derzeit durch die Plattformverwaltung
  gesteuert.

Der Administrator des ursprünglichen Kundenbereichs kann unter
**Administration → Kundenbereiche und Abonnements** einen Kunden samt erstem
Administrator anlegen. Der Kunde sieht unter **Mein Bereich** ausschließlich
seine Kennzahlen und Einstellungen.

## Sicherer Geräte-Ingest über das Internet

Für ein Mikrofon wird unter **Mikrofone** einmalig ein Gerätegeheimnis
ausgestellt. Es wird nur bei der Erstellung angezeigt und ausschließlich als
SHA-256-Prüfwert gespeichert. Das Gerät sendet über Caddy/HTTPS an die
vorhandenen Ingest-Endpunkte mit:

```text
X-Device-Id: <Geräte-ID>
X-Device-Secret: <einmal angezeigtes Geheimnis>
```

Die Geräte-ID im Nutzdatenkörper muss mit dem Zugang übereinstimmen. Ein
widerrufenes oder neu ausgestelltes Geheimnis macht das vorherige sofort
ungültig. Der bisherige globale Ingest-Schlüssel bleibt nur für die lokalen
Bestandsgeräte kompatibel und soll bei externen Kundengeräten nicht verwendet
werden.

## Betriebs- und Datenschutzgrenzen

- Audio- und Personendaten benötigen pro Kundenbereich eine dokumentierte
  Rechtsgrundlage, Löschfrist und Zugriffskontrolle.
- Direkter Zugriff auf Port 8015 bleibt gesperrt; extern wird ausschließlich
  HTTPS über Caddy freigegeben.
- Vor einer Vermarktung fehlen noch Zahlungsanbieter/Webhooks, automatisierte
  Kündigung und Löschung, Rechnungen/Steuern, AGB und eine juristisch geprüfte
  Auftragsverarbeitung.

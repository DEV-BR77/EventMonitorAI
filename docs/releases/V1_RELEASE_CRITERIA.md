# Verbindliche Release-Kriterien für v1.0

Ein v1.0-Tag darf erst erstellt werden, wenn jedes Pflichtkriterium mit Datum,
Commit und Prüfnachweis im Releaseprotokoll belegt ist.

## Pflichtkriterien

- [ ] Roadmap Phasen 0–9 sind implementiert, getestet und dokumentiert.
- [ ] Arbeitsverzeichnis ist sauber; Commit und Remote-Branch sind identisch.
- [ ] `python scripts/check_project.py`, Ruff, Black, JavaScript-Syntax und die
      vollständige Pytest-Suite sind grün.
- [ ] CI und Release-Workflow sind für den Kandidaten grün.
- [ ] Release-ZIP enthält keine Geheimnisse/Laufzeitdaten; SHA-256 stimmt.
- [ ] Neuinstallation auf sauberem Windows-Docker-Desktop-System ist erfolgreich.
- [ ] Upgrade einer gesicherten Vorversion und dokumentierter Rollback sind erfolgreich.
- [ ] Automatisches und manuelles Backup wurden erstellt; Prüfsummen und
      `pg_restore --list` sind gültig; ein Restore wurde auf einer getrennten
      Testdatenbank geprobt.
- [ ] Mindestens 24 Stunden Soak-Test auf Zielhardware: keine ungeplanten
      Neustarts, keine verlorenen Datenbankverbindungen, kein unbeschränktes
      Speicherwachstum, Fehlerquote ≤0,1 %, p95 der vereinbarten API-Endpunkte
      <500 ms.
- [ ] Security-/Datenschutzreview enthält keine offenen kritischen oder hohen
      Befunde; direkte Portfreigaben sind gesperrt und TLS ist gültig.
- [ ] Zwei Mikrofone liefern plausibel kalibrierte Werte; CSV-Vergleich ist
      dokumentiert; Wind und „Kein Lärm“ verhalten sich wie vorgesehen.
- [ ] Rollen Admin/Operator/Betrachter, Live-Audio-Freigabe, Push,
      Home Assistant, Audio-Wiedergabe und Mobilansicht sind abgenommen.
- [ ] Betreiber hat Rechtsgrundlage, Datenschutzhinweise, Lösch- und
      Aufbewahrungsfristen für reale Audio-/Personendaten festgelegt.
- [ ] `VERSION`, Changelog, README, Release Notes und OCI-Tag stimmen überein.

## Freigabeentscheidung

Ein fehlender Nachweis gilt als **nicht bestanden**. Zeitdruck, ein grüner
Health-Endpunkt oder eine erfolgreiche Teiltestsuite ersetzen kein Kriterium.
Die technische Freigabe und die Betreiber-/Datenschutzfreigabe werden getrennt
dokumentiert.

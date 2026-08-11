# Phase 11 – EventMonitor Voice

Stand: ausführbarer Flutter-Prototyp, noch keine Store-Beta

## Architektur

`mobile/` ist eine unabhängige Flutter-Anwendung für Android und iOS. Sie
verwendet die bestehende FastAPI-Anmeldung. Der signierte Zugriffstoken enthält
die Tenant-ID; die zentrale SQLAlchemy-Isolation filtert Geräte, Ereignisse und
Lärmprotokolle. Die App speichert Token und Zuordnung ausschließlich über den
geschützten Systemspeicher.

Die Messpipeline liest während einer sichtbaren Sitzung Mono-PCM mit 16 kHz.
Sie berechnet RMS-basierte Pegelwerte, Sitzungsstatistiken und ein einfaches
Hann-gefenstertes Frequenzspektrum. Das ist eine technische Orientierung, keine
geeichte oder normgerechte Schallpegelmessung. Ein lokaler Offset dokumentiert
die erkannte Geräteabweichung; eine produktive Freigabe verlangt eine
Vergleichsmessung je unterstütztem Gerätemodell.

## Datenschutz und Plattformgrenzen

- Mikrofonzugriff erfolgt erst nach Einwilligungsinformation und Systemfreigabe.
- Die laufende Messung ist dauerhaft im UI sichtbar.
- Beim Wechsel in den Hintergrund wird die Sitzung beendet. Damit werden die
  unterschiedlichen Android-/iOS-Hintergrundregeln nicht umgangen.
- Der Prototyp verarbeitet PCM lokal und überträgt kein Audio.
- Serververbindungen sind ausnahmslos nur per HTTPS zulässig.
- Abmeldung löscht Token, Tenant-, Geräte- und Einwilligungsstatus lokal.
- Die Geräteauswahl stammt ausschließlich aus dem authentifizierten Tenant.
  Eine künftige Smartphone-Ingest-Freigabe muss widerrufbare, gerätegebundene
  Zugangsdaten verwenden; Benutzer-Tokens dürfen nicht als dauerhafte
  Gerätegeheimnisse dienen.

## Prüfstand und offene Abnahme

`flutter analyze` und `flutter test` laufen auf Windows mit Flutter 3.44.9.
Die automatisierten Tests prüfen insbesondere, dass der Bereitschaftszustand
keine scheinbar gültigen Nullwerte darstellt und dass die Anmeldung den sicheren
Zugriff transparent beschreibt.

Noch offen und deshalb in der Roadmap nicht abgehakt sind Registrierung und
Tarifentscheidung, produktiver Smartphone-Ingest, Push, Export, Löschworkflow,
Tests auf realen Android-/iPhone-Geräten, Security-Abnahme und Store-Vorbereitung.
Store-Konten, Gebühren sowie verbindliche Rechts- und Einwilligungstexte
benötigen externe Entscheidungen und werden nicht vorweggenommen.

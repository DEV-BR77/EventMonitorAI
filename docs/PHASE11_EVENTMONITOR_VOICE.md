# Phase 11 – EventMonitor Voice

Stand: ausführbarer Flutter-Prototyp und lokal verifizierte Android-Debug-APK,
noch keine Store-Beta

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

Digitale Stille (PCM ohne verwertbare Amplitude) wird ausdrücklich nicht als
20-dB-Messwert ausgegeben. Die laufende Sitzung zeigt stattdessen einen Hinweis
auf den fehlenden Geräte- beziehungsweise Emulator-Audioeingang. Ein Eintrag
aus der Server-Ereignisliste wird im Live-Bildschirm als letztes
Server-Ereignis bezeichnet und nicht als gegenwärtige lokale KI-Erkennung.

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
Zugriff transparent beschreibt. Zusätzlich wird geprüft, dass ein digital
stummer PCM-Puffer als RMS 0 erkannt wird und nicht in einen scheinbaren
Schallpegel umgewandelt werden kann.

Noch offen und deshalb in der Roadmap nicht abgehakt sind Registrierung und
Tarifentscheidung, produktiver Smartphone-Ingest, Push, Export, Löschworkflow,
Tests auf realen Android-/iPhone-Geräten, Security-Abnahme und Store-Vorbereitung.
Store-Konten, Gebühren sowie verbindliche Rechts- und Einwilligungstexte
benötigen externe Entscheidungen und werden nicht vorweggenommen.

## Android-Build und Weg zu Google Play

Die lokale Android-Toolchain besteht aus OpenJDK 17, Android SDK 36,
Build-Tools 36.0.0, NDK 28.2.13676358 und CMake 3.22.1. Der geprüfte
Debug-Build wird mit folgendem Befehl erzeugt:

```powershell
flutter build apk --debug
```

Das Ergebnis `mobile/build/app/outputs/flutter-apk/app-debug.apk` dient nur der
direkten Installation und dem Realgerätetest. Es ist mit einem Debug-Schlüssel
signiert, bleibt durch `.gitignore` vom Repository ausgeschlossen und ist kein
Google-Play-Release.

Nach Freigabe der in `docs/Roadmap.md` dokumentierten externen Entscheidungen
wird ein gesonderter Upload-Key außerhalb von Git eingerichtet. Der Store-Build
erfolgt anschließend als signiertes Android App Bundle:

```powershell
flutter build appbundle --release
```

Das erwartete Artefakt ist
`mobile/build/app/outputs/bundle/release/app-release.aab`. Erst nach
Signaturprüfung, Datenschutz- und Security-Abnahme, Realgerätetest und
erfolgreichem internen sowie geschlossenem Play-Test darf dieses Release in die
Produktion überführt werden. Der detaillierte, verbindliche Ablauf und seine
Stopppunkte stehen im Abschnitt „Verbindlicher Google-Play-Live-Weg“ der
Roadmap.

## Direkte Android-Vorschau

Für Tests vor einer Google-Play-Entscheidung existiert ein getrennter
Sideload-Kanal. Er verwendet bewusst nicht die spätere Store-Paketkennung:

```text
de.eventmonitor.eventmonitor_voice.preview
```

Der Build wird release-kompiliert, aber mit einem ausschließlich für die
Vorschau bestimmten RSA-3072-Schlüssel signiert. Schlüssel und DPAPI-geschütztes
Kennwort liegen lokal außerhalb des Repositorys unter
`C:\Users\Bjoern\.codex\secrets\EventMonitorAI`. Dieser Ordner muss für weitere
Preview-Updates gesichert werden; ohne denselben Schlüssel kann Android eine
neue Version nicht über die installierte Vorschau aktualisieren.

Version 0.1.0 wird als GitHub-Prerelease unter dem festen Dateinamen
`eventmonitor-voice-preview-0.1.0.apk` veröffentlicht. Die Downloadseite
`https://eventmonitor.eu/android-download.html` nennt Version, Dateigröße,
Paketkennung, Installationsschritte und SHA-256. Die Binärdatei bleibt ein
Build-Artefakt und wird nicht in Git aufgenommen.

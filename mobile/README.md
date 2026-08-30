# EventMonitor Voice

Gemeinsamer Flutter-Prototyp für Android und iOS. Die App meldet sich am
vorhandenen EventMonitorAI-Backend an, zeigt ausschließlich Daten des im Token
gebundenen Kundenbereichs und führt eine ausdrücklich gestartete lokale
Mikrofonmessung durch.

## Funktionsumfang

- Anmeldung per HTTPS und verschlüsselte Ablage des kurzlebigen Zugriffstokens
  in Android Keystore beziehungsweise iOS Keychain
- Auswahl eines Messpunkts aus dem eigenen Kundenbereich
- sichtbare Vordergrund-Messsitzung mit aktuellem dB(A)-Näherungswert,
  MIN/MAX/AVG und Frequenzbändern von 31,5 Hz bis 8 kHz
- lokaler Kalibrier-Offset mit deutlichem Hinweis auf die Geräteabweichung
- KI-Vorschlag aus dem jüngsten Serverereignis
- Navigation zu Ereignissen und ELM-/Lärmprotokoll
- automatisches Beenden der Messung beim Verlassen des Vordergrunds

Der Prototyp lädt keine Audiodaten hoch und behauptet keine geeichte Messung.
Die numerische Pegelanzeige ist erst nach Vergleichskalibrierung sinnvoll.

## Entwicklung

```powershell
flutter pub get
flutter analyze
flutter test
flutter run --flavor production
flutter build apk --flavor production --debug
```

Die Android-Konfiguration verwendet bewusst eine nicht inkrementelle
Kotlin-Kompilierung. Dadurch bleiben Builds unter Windows stabil, wenn der
globale Pub-Cache auf `C:` und der Repository-Worktree auf `D:` liegt.

Auch Entwicklungsserver müssen per HTTPS erreichbar sein. Android und iOS
fragen die Mikrofonberechtigung beim ersten Start einer Messsitzung an.

## Grenzen des Prototyps

- keine Hintergrundaufnahme oder Foreground-Service-Umgehung
- keine Audio-, Foto- oder Videoübertragung
- noch keine native Push-Registrierung
- keine Store-Signierung, Store-Konten oder Veröffentlichungsmetadaten
- iOS-Build und reale Mikrofontests benötigen macOS/Xcode und ein physisches
  iPhone; Android-Realmessungen benötigen ein physisches Android-Gerät

## Öffentliche Android-Vorschau

Die öffentlich herunterladbare Vorschau verwendet den Flavor `preview`, die
separate Paketkennung `de.eventmonitor.eventmonitor_voice.preview` und einen
eigenen, außerhalb von Git aufbewahrten Signaturschlüssel. Dadurch bleibt die
spätere Play-Store-Identität unabhängig. Ein signierter Build benötigt diese
Umgebungsvariablen:

```text
EVENTMONITOR_ANDROID_PREVIEW_KEYSTORE
EVENTMONITOR_ANDROID_PREVIEW_STORE_PASSWORD
EVENTMONITOR_ANDROID_PREVIEW_KEY_PASSWORD
```

Buildbefehl:

```powershell
flutter build apk --flavor preview --release
```

Das Ergebnis liegt unter
`build/app/outputs/flutter-apk/app-preview-release.apk`. Keystore, Kennwörter
und APK werden nicht eingecheckt. Veröffentlichte Dateien erhalten eine
SHA-256-Prüfsumme und werden als GitHub-Prerelease bereitgestellt.

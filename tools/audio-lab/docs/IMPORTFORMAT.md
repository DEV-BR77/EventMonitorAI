# Messdaten und Importformat

## Erwartetes Messpaket

Ein ZIP-Paket benötigt mindestens:

```text
Messung.zip
├─ db.csv
└─ aufnahme.wav
```

Optional:

```text
├─ extended.csv
└─ extended_logarithm.csv
```

Die Dateien dürfen in Unterordnern des ZIP-Pakets liegen.

## `db.csv`

Die Datei enthält den zeitlichen Schallpegelverlauf. Erwartete Spalten:

- `Date`
- `Time`
- `Current (dB-A)`
- `Max (dB-A)`
- eine Spalte mit `Average` im Namen

AudioLab interpretiert wiederholte Zeitstempel innerhalb derselben Sekunde als Messungen im Abstand von 0,2 Sekunden. Dies entspricht fünf Messwerten pro Sekunde bei den aktuell vorliegenden Exporten.

## `extended.csv`

Enthält ein lineares Frequenzspektrum der gesamten Aufnahme mit:

- Frequenz
- `MIN`
- `MAX`
- `AVG`

## `extended_logarithm.csv`

Enthält eine logarithmisch gruppierte Darstellung des Gesamtspektrums.

Die beiden Extended-Dateien besitzen keine zeitliche Zuordnung zu einzelnen Ereignissen. Für spätere segmentbezogene Frequenzanalysen muss deshalb ein Spektrogramm direkt aus der Audiodatei berechnet werden.

## Audiodateien

Unterstützte Dateiendungen:

- WAV
- MP3
- FLAC
- OGG
- M4A

Empfehlung:

- WAV
- 16 Bit oder 24 Bit PCM
- 16 kHz bis 48 kHz
- mono oder stereo

## Dublettenprüfung

Für jede ZIP-Datei wird ein SHA-256-Hash berechnet. Ein identisches Paket wird nicht erneut importiert.

Bei bereits entpackten Verzeichnissen basiert die aktuelle Prüfung nur auf dem Pfad. Für den produktiven Ausbau sollte auch für Verzeichnisimporte ein Inhaltsmanifest gehasht werden.

## Zeitbezug

Der Startzeitpunkt der Aufnahme wird aus dem ersten Datensatz in `db.csv` übernommen. Audio und CSV gelten aktuell als gleichzeitig gestartet.

Für robuste Massenimporte sollte später geprüft werden:

- Differenz zwischen Audio- und CSV-Dauer
- Zeitzone und Sommerzeit
- fehlende Messwerte
- unterbrochene Aufnahmen
- driftende Zeitbasen

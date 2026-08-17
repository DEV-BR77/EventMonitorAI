# Mehrmikrofon-Kalibrierung

Die Dashboard-Ansicht **Mikrofone** erfasst alle aktuell online gemeldeten
Sensoren gleichzeitig. Für jeden der drei Bereiche **Leise**, **Mittel** und
**Laut** wird ein bekannter Referenzpegel eingetragen und gemeinsam mit den
aktuellen Messwerten gespeichert.

## Ablauf

1. Mikrofone möglichst nah beieinander und gleich ausgerichtet positionieren.
2. Eine stabile Referenzquelle für den gewählten Pegelbereich abspielen.
3. Den Wert eines geeigneten Referenzmessgeräts im Dashboard eintragen.
4. **Alle Online-Mikrofone erfassen** wählen.
5. Den Ablauf für die beiden übrigen Pegelbereiche wiederholen.

Das Protokoll bewahrt Referenz- und Messwert getrennt auf. Der empfohlene
Offset ist der Mittelwert der vorhandenen Differenzen
`Referenzwert - Messwert`. Dadurch bleiben Abweichungen zwischen leisem,
mittlerem und lautem Bereich sichtbar; ein einzelner globaler Offset täuscht
keine nicht vorhandene Linearität vor.

Die Funktion dient der nachvollziehbaren Vergleichskalibrierung. Sie ersetzt
keine zertifizierte oder behördlich anerkannte Schallpegelmessung.

## Direktvergleich mit Display-Messgerät

In **Live-Ereignisse → Live-Pegel und Direktkalibrierung** werden alle aktiven
Mikrofone getrennt mit ihrem aktuellen dB(A)-Wert angezeigt. Der Raspberry Pi
meldet den Pegel alle zwei Sekunden. Für ein Klasse-2-Messgerät ohne Export wird
der am Display abgelesene Wert direkt beim betreffenden Mikrofon eingetragen.
**Erfassen und anwenden** berechnet den neuen Offset aus dem gleichzeitig
vorliegenden Mikrofonwert und aktiviert ihn sofort.

Die Änderung gilt für alle danach eintreffenden Werte. Zusätzlich werden die
bereits gespeicherten Ereignispegel, Durchschnittspegel und Zeitreihen dieses
Mikrofons um genau die Änderung zwischen vorherigem und neuem Offset korrigiert.
Audioclips werden nicht verändert. Der Direktabgleich ist auf ±30 dB begrenzt
und wird abgelehnt, wenn der letzte Mikrofonwert älter als 15 Sekunden ist.

## Zeitreihe aus einem Referenzmessgerät

Für eine belastbarere Vergleichsmessung kann unter **Mikrofone →
CSV-Referenzmessung abgleichen** eine ein- bis dreiminütige Zeitreihe
importiert werden. Die CSV muss UTF-8-kodiert sein und mindestens zwölf Werte
enthalten. Unterstützt werden beispielsweise:

```csv
timestamp;reference_db
2026-08-09T04:00:00+02:00;38,4
2026-08-09T04:00:05+02:00;39,1
```

Alternativ sind die deutschen Spaltennamen `zeit`, `uhrzeit`, `zeitstempel`
und `dezibel` zulässig. Reine Uhrzeiten werden dem aktuellen Kalendertag in
`Europe/Berlin` zugeordnet. Für jeden gespeicherten Fünf-Sekunden-Wert wird
innerhalb der gewählten Toleranz der zeitlich nächste Referenzwert verwendet.

Das Ergebnis zeigt Trefferzahl, Mittelwerte, mittlere Differenz und den
mittleren absoluten Fehler (MAE). Der Offset wird bewusst nicht automatisch
aktiviert. Erst **Offset anwenden** übernimmt ihn für neue Werte und korrigiert
bereits gespeicherte Ereignispegel, Durchschnittspegel und Zeitreihen desselben
Mikrofons um die Offsetänderung. Zum Schutz vor fehlerhaften Dateien ist der
Offset auf ±30 dB begrenzt.

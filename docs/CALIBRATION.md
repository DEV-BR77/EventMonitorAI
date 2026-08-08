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

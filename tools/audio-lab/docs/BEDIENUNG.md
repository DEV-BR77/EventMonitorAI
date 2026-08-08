# Bedienungsanleitung

## 1. Übersicht

Die Übersicht zeigt:

- Anzahl importierter Aufnahmen
- gesamte Audiodauer
- Anzahl erzeugter Segmente
- Anzahl bereits bestätigter Segmente
- Liste der importierten Aufnahmen

## 2. Messungen importieren

### Einzelne ZIP-Dateien

1. **Import** öffnen.
2. Eine oder mehrere ZIP-Dateien auswählen.
3. **Ausgewählte Dateien importieren** anklicken.
4. Den Status je Datei prüfen.

### Ganzen Messordner importieren

1. Den vollständigen lokalen Ordnerpfad eintragen.
2. **Ordner importieren** anklicken.
3. AudioLab durchsucht alle Unterordner nach ZIP-Dateien.
4. Bereits vorhandene Messungen werden übersprungen.
5. Fehler werden je Datei protokolliert.

### Importprotokoll und Fortsetzung

Unterhalb der Importfunktionen zeigt das Importprotokoll Quelle, Status,
Versuchsanzahl, Aufnahme-ID, Fehlergrund sowie Start- und Endzeit. Hochgeladene
ZIP-Dateien bleiben dafür im lokalen `data/inbox` erhalten. Mit
**Fehlgeschlagene oder unterbrochene Importe fortsetzen** werden alle noch
verfügbaren Quellen erneut verarbeitet; erfolgreiche Aufnahmen werden durch
die Hash-Dublettenprüfung nicht doppelt angelegt.

Beispiel:

```text
D:\Laermmessungen\2026
```

## 3. Ereignisse lernen

1. **Ereignisse lernen** öffnen.
2. Eine Aufnahme auswählen.
3. Die Sortierung wählen:
   - Auffälligste zuerst
   - Lauteste zuerst
   - Chronologisch
4. Den Audioausschnitt anhören.
5. Eine Lärmart auswählen.
6. Sicherheit und optionale Notiz ergänzen.
7. **Bestätigen und speichern** anklicken.

Mit **Vorheriges Segment** und **Nächstes Segment** lässt sich die aktuelle
Sortierung ohne manuelle Positionsangabe durchlaufen. Der dB-Verlauf zeigt die
gesamte Aufnahme, hebt das ausgewählte Segment hervor und kann horizontal
gezoomt und verschoben werden. Darunter stellt das Spektrogramm den gewählten
Audioausschnitt einschließlich Vor- und Nachlauf nach Zeit, Frequenz und
relativem Pegel dar.

Der Vor- und Nachlauf hilft, den Kontext eines kurzen Segments zu hören. Die gespeicherte Segmentgrenze bleibt dabei unverändert.

### Ereignis zuschneiden

Start und Ende können in 0,1-Sekunden-Schritten innerhalb der Aufnahme angepasst
werden. Beim Speichern berechnet AudioLab Peak, Mittelwert und Auffälligkeit für
den neuen Bereich. **Auf Ursprung zurücksetzen** stellt die beim Import erzeugten
Grenzen wieder her. Der Download liefert nur den exakt markierten Bereich als WAV;
der eingestellte Hör-Vor-/Nachlauf wird nicht exportiert.

## Backup und Datenmigration

Unter **Sicherung** erzeugt AudioLab eine portable `.emabackup`-Datei mit einer
konsistenten SQLite-Kopie, allen importierten Audiodateien, Formatversion und
SHA-256-Prüfsummen. Vor einer Wiederherstellung werden sämtliche Inhalte und die
Datenbankintegrität geprüft. Die vorhandene Datenbank wird zusätzlich als
zeitgestempelte `.pre-restore-…sqlite3`-Rückfallkopie aufbewahrt. Damit kann die
Sicherung auch zur Migration auf einen anderen Rechner verwendet werden; die
gespeicherten Audiopfade werden dabei auf die neue Bibliothek umgestellt.

## 4. Empfohlene Arbeitsweise

Zuerst die auffälligsten Segmente bearbeiten. Dadurch werden relevante Ereignisse schneller gefunden als bei rein chronologischer Prüfung.

Für jedes Ereignis möglichst:

- nur die tatsächlich hörbare Lärmart auswählen
- bei Unsicherheit `Unklar` verwenden
- keine Person oder Ursache behaupten, die nicht akustisch belegbar ist
- Besonderheiten in der Notiz festhalten
- ähnliche Geräusche konsistent benennen

## 5. Auswertung

Der Bereich **Auswertung** zeigt bestätigte Ereignisse und ihre Häufigkeit. Kategorien können gefiltert werden.

Der CSV-Export enthält unter anderem:

- Aufnahmebeginn
- Start und Ende des Segments
- maximalen dB(A)-Wert
- mittleren dB(A)-Wert
- bestätigte Kategorie
- Sicherheit
- Notiz

## 6. Datensicherung

Regelmäßig sichern:

```text
data/eventmonitor.sqlite3
data/library/
```

Datenbank und Audiobibliothek gehören zusammen. Wird nur die Datenbank gesichert, fehlen später die zugehörigen Audiodateien.

# Kategorien und Lernworkflow

## Ziel

Der Lernworkflow erzeugt einen geprüften Trainingsdatensatz aus historischen Aufnahmen. Eine automatische Vorhersage darf ein menschlich bestätigtes Label nicht ersetzen.

## Kernkategorien

| Kategorie | Verwendung |
|---|---|
| Schreien | sehr laute oder stark angespannte menschliche Stimme |
| Rufen | einzelne oder kurze laute Zurufe |
| Streit / mehrere Stimmen | überlagerte oder wechselnde laute Stimmen |
| Schlagen / Aufprall | harter, kurzer oder wiederholter Impuls unbekannter Ursache |
| Türknallen | klar als Tür oder Tor erkennbarer Impuls |
| Auto / Vorbeifahrt | Pkw-Geräusch, Anfahrt, Abfahrt oder Vorbeifahrt |
| Motorrad | typisches Motorrad- oder Rollergeräusch |
| Hupe | Fahrzeughupe |

## Referenz- und Negativklassen

- Normales Sprechen
- Hund
- Musik
- Maschine
- Wind / Regen
- Hintergrund
- Unklar

Negativklassen sind wichtig. Ein Modell lernt nur dann sauber, Schreien oder Schlagen zu erkennen, wenn es auch ähnliche, aber nicht relevante Geräusche kennt.

## Abgrenzung

### Schreien oder Rufen

- **Rufen:** kurz, meist einzelne Wörter oder kurze Äußerungen
- **Schreien:** intensiver, länger, wiederholt oder deutlich emotionaler Klang
- bei fehlender Klarheit `Unklar` oder eine gemeinsame Zwischenklasse verwenden

### Schlagen oder Türknallen

Nur `Türknallen` verwenden, wenn der Klang eindeutig als Tür oder Tor erkennbar ist. Andernfalls `Schlagen / Aufprall`.

### Auto oder Motorrad

Bei unsicherer Fahrzeugart zunächst eine allgemeinere Fahrzeugklasse verwenden. Eine falsche feine Kategorie ist für das Training schädlicher als eine korrekte grobe Kategorie.

## Sicherheitswert

- `1,00`: eindeutig
- `0,80–0,95`: sehr wahrscheinlich
- `0,60–0,75`: plausibel, aber nicht eindeutig
- unter `0,60`: besser `Unklar`

## Qualitätsregeln für Trainingsdaten

- nur bestätigte Labels trainieren
- keine automatisch erzeugten Labels ungeprüft zurücktrainieren
- gleiche Ereignisse nicht unnötig mehrfach aus fast identischen Segmenten verwenden
- verschiedene Tageszeiten, Wetterlagen und Entfernungen abdecken
- Klassen möglichst ausgewogen halten
- Originalaudio unverändert lassen
- jede Modellversion dokumentieren

## Empfohlener Umfang

Für einen ersten technischen Test:

- mindestens 20 bestätigte Segmente
- mindestens zwei Kategorien

Für eine belastbarere lokale Erkennung:

- etwa 100 bis 300 vielfältige Segmente je Kernkategorie
- zusätzlich ausreichend Hintergrund- und Verwechslungsklassen

Die Qualität und Vielfalt der Beispiele ist wichtiger als eine bloß hohe Anzahl nahezu identischer Segmente.

# Trainings-, Validierungs- und Testaufteilung

AudioLab teilt gelabelte Daten ausschließlich auf Ebene vollständiger Aufnahmen
auf. Segmente derselben Ursprungsaufnahme können dadurch nie gleichzeitig im
Training und in der Qualitätsmessung vorkommen. Das verhindert eine sonst leicht
übersehene Datenleckage durch fast identische, benachbarte Audioausschnitte.

Die Split-Version `1.0.0` verwendet standardmäßig 70 % der Aufnahmen für das
Training und jeweils 15 % für Validierung und Test. Mindestens drei unabhängige
Aufnahmen sind erforderlich. Ein gespeicherter JSON-Manifest enthält:

- Zufalls-Seed und Split-Anteile
- eindeutige Zuordnung jeder Aufnahme
- Segment- und Klassenanzahl je Teilmenge
- Fingerprint der verwendeten Feature-Pipeline

Bei identischem Seed und identischer Aufnahmeliste ist die Aufteilung vollständig
reproduzierbar. Der Testsatz bleibt bis zur abschließenden Modellbewertung
unangetastet; Parameterentscheidungen erfolgen nur mit Training und Validierung.

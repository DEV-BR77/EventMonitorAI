# Cases und Teilereignisse

Ein Case fasst ein oder mehrere Ereignisse zu einem dokumentierbaren Vorfall
zusammen. Die Ereignisse dürfen aus unterschiedlichen Aufnahmen stammen, benötigen
aber jeweils einen absoluten Aufnahmebeginn.

Beim Erstellen berechnet AudioLab:

- den frühesten absoluten Beginn;
- das späteste absolute Ende;
- die gesamte Zeitspanne einschließlich Pausen;
- die chronologische Reihenfolge aller Teilereignisse.

Ein Ereignis kann nur zu einem Case gehören. Sobald ein automatisch gruppiertes
Ereignis verknüpft ist, wird es bei späteren Neuaufbauten geschützt, damit der Case
nicht unbemerkt seine Belegkette verliert. Nicht verknüpfte automatische Ereignisse
werden weiterhin anhand der aktuellen Gruppierungsversion neu erzeugt.

Cases werden im Bereich **Ereignisse** angelegt und mit Beginn, Ende, Dauer,
Status und ihrer geordneten Teilereignisliste angezeigt.

# Active Learning

Die Reihenfolge **Active Learning** stellt offene Segmente nach ihrem erwarteten
Lernwert bereit. Der Score kombiniert zwei nachvollziehbare Größen:

- 75 % Unsicherheit: normalisierte Entropie der Klassenwahrscheinlichkeiten;
- 25 % Informationsgehalt: normalisierte Distanz zum Zentrum der bisher vom
  Trainings-Scaler gesehenen Feature-Verteilung.

Ein Wert nahe 1 bedeutet hohe Priorität. Unsichere Grenzfälle stehen damit vor
bereits eindeutig erkannten Beispielen; zugleich können ungewöhnliche Signale
sichtbar werden. Unsicherheit, Informationsgehalt und kombinierter Score werden
mit dem jeweiligen Modellvorschlag gespeichert und bleiben auditierbar.

Active Learning vergibt selbst kein Trainingslabel. Erst die menschliche
Bestätigung oder Korrektur in **Ereignisse lernen** macht das Segment zu einem
zulässigen Trainingsbeispiel.

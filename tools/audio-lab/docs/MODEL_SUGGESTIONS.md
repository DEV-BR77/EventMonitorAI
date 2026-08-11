# Modellvorschläge bestätigen und korrigieren

Unter **Modelltraining** kann ein lokales Modell alle noch offenen Segmente
klassifizieren. AudioLab speichert je Vorschlag Modellname, Klasse,
Wahrscheinlichkeit und Erstellungszeit.

In **Ereignisse lernen** erscheint die vorgeschlagene Klasse samt Konfidenz und
wird als Vorauswahl angeboten. Der Mensch hört das Segment weiterhin selbst an:

- unverändert speichern bestätigt den Vorschlag;
- eine andere Klasse auswählen und speichern korrigiert ihn.

Zu jedem Review werden Zeitpunkt, tatsächlich gewählte Klasse und die Information
gespeichert, ob der Vorschlag korrekt war. Automatische Vorschläge werden niemals
ungeprüft als Trainingslabel übernommen; ausschließlich das bestätigte Segmentlabel
fließt in spätere Trainingsläufe ein.

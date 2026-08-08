# Personenverwaltung und personenbezogene Lärmereignisse

AudioLab verwaltet Personen als eigene, editierbare Datensätze mit frei wählbarem
Namen und Aktivstatus. Ein Segment kann genau einer Person zugeordnet werden; die
Zuordnung ist optional und speichert Quelle, Konfidenz und Bestätigungszeit.

Wenn für bestätigte Beispiele einer Person modellkompatible Audio-Embeddings
vorliegen, bildet AudioLab daraus ein Profilzentrum. Für ein neues Segment wird
die ähnlichste aktive Person vorgeschlagen. Dieser Vorschlag ist nur eine
Arbeitshilfe: Erst das Speichern in **Ereignisse lernen** bestätigt oder ändert die
Personenzuordnung. Dadurch wird insbesondere das wiederkehrende Prüfen von Rufen
und Schreien unterstützt, ohne eine automatische Identität als Tatsache auszugeben.

Der Bereich **Personen** zeigt getrennte Statistiken nach:

- Person
- Beurteilungszeit (Tag, Tagesruhe, Abend oder Nacht)
- Lärmkategorie
- Häufigkeit
- aufsummierter Ereignisdauer

Personen können umbenannt oder deaktiviert werden. Historische Zuordnungen und
Statistiken bleiben beim Deaktivieren erhalten.

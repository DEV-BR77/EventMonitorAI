# Zeitliche Ereignisgruppierung

Bestätigte Segmente werden mit der versionierten Gruppierungsregel `1.0.0` zu
zusammenhängenden Ereignissen verbunden. Die Regel arbeitet ausschließlich
innerhalb derselben Ursprungsaufnahme und verwendet folgende maximale Pausen:

- Rufen, Schreien und Streit/mehrere Stimmen: 3,0 Sekunden
- Hupe, Schlagen/Aufprall und Türknallen: 1,5 Sekunden
- identische sonstige Kategorien: 1,0 Sekunde

Unterschiedliche Stimmkategorien dürfen damit zu demselben länger andauernden
Stimmereignis gehören. Ebenso werden eng aufeinanderfolgende Impulse als eine
Impulsserie behandelt. Andere Kategorien werden nur mit derselben Klasse
verbunden.

Jedes Ereignis speichert Anfang, Ende, Hauptklasse, Familie, Segmentanzahl,
Peak-/Mittelpegel und die verwendete Regelversion. Eine separate Verknüpfungstabelle
bewahrt die geordnete Liste aller Teilsegmente. Der Neuaufbau ist transaktional und
idempotent; manuell erzeugte Ereignisse werden dabei nicht gelöscht.

Unter **Ereignisse** kann die Gruppierung neu aufgebaut und mit ihren Kennwerten
kontrolliert werden.

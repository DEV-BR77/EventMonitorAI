# Phase 8 – Audio-Lab im Dashboard

Das geschützte Dashboard enthält für Operatoren und Administratoren einen eigenen Bereich
**Audio-Lab**. Er nutzt denselben Ereignis- und Klassenbestand wie die Live-Ansicht und benötigt
keine zweite Datenhaltung.

## Prüfworkflow

- Klassenkacheln zeigen offene und erledigte Ereignisse je erkannter Klasse sowie „Unbekannt“.
- Die Warteschlange lässt sich je Klasse und Status filtern.
- Mehrere sichtbare Ereignisse können ausgewählt und mit einer gemeinsamen Basis- und
  Feinzuordnung bestätigt werden. Jede Sammeländerung erzeugt pro Ereignis einen Audit-Eintrag.
- Offene unbekannte, offene erkannte, erledigte unbekannte und erledigte erkannte Ereignisse
  werden getrennt gezählt.

## Automatische und nächtliche Prüfläufe

Ein Prüflauf verarbeitet Ereignisse in begrenzten Paketen und speichert nach jedem Paket den
zuletzt geprüften Ereignisbezeichner. Er kann unterbrochen und später ab genau dieser Position
fortgesetzt werden. Automatische Läufe wenden den aktuellen Klassenkatalog erneut auf die
unveränderte ursprüngliche Modellerkennung an. Manuell bestätigte Zuordnungen werden niemals
überschrieben.

Ab zwei manuellen, für dasselbe ursprüngliche Modelllabel vollständig übereinstimmenden
Zuordnungen wird die Klasse automatisch verwendet; ab drei Bestätigungen sind
mindestens 80 Prozent Eindeutigkeit erforderlich. Die Lernregel gilt für neue und
noch offene gleichartige Ereignisse. Ist nur die Basisklasse eindeutig, bleibt das
Ereignis mit dieser Vorauswahl bis zur manuellen Feinzuordnung offen. Bei Stimmereignissen überbrückt zusätzlich ein
enger Zeitkontext von zwölf Sekunden unterschiedliche Modelllabels beider Mikrofone,
etwa „Sprache“ und eine fälschliche „Katze“-Erkennung. Automatisch gelernte Treffer
gelten als erledigt, bleiben aber korrigierbar. Wind, Umgebung und technische Störungen
sind lernfähig, aber standardmäßig aus Lagebild, Statistik und Live-Strom
ausgeblendet. Sie bleiben in der Audio-Lab-Prüfung sichtbar.

Die früher getrennten Feinzuordnungen „Anhaltendes Rufen“ und „Lautes Schreien“ sind
als **Lautes Rufen/Geschrei** zusammengeführt. Die akustische Abgrenzung war im realen
Einsatz nicht stabil genug. Vorhandene Ereignisse werden auf die gemeinsame Klasse
überführt; „Streit / mehrere Personen“ bleibt separat.
Gelernte Zuordnungen werden im Live-Strom als vorausgefüllter Vorschlag angezeigt und
bleiben offen, bis ein Benutzer sie mit **Übernehmen** bestätigt. Dadurch entfallen die
Auswahlklicks, ohne dass ein Lernvorschlag ungeprüft als erledigt gilt.

Die Klasse **Kein Lärm / verwerfen** entfernt Ereignis und Audioclip. Nur ein
normalisiertes Modelllabel und die Zahl der Bestätigungen bleiben als
anonymes Lernmuster erhalten. Nach drei Bestätigungen werden gleichartige
Treffer bereits vor der Speicherung verworfen; Zeit, Pegel und Audio werden
dann nicht persistiert.

Personenprofile werden im Audio-Lab manuell angelegt. Erst bestätigte
Zuordnungen von Stimmereignissen dürfen in Häufigkeitsstatistiken und spätere
akustische Ähnlichkeitsprofile einfließen. Ein Profil ist kein Beweis für die
Identität einer Person.

## Stimmgruppenprüfung und Personenverwaltung

Anonyme Stimmgruppen besitzen eine persistente Einzelprüfung. Administratoren können
zugeordnete Clips anhören, bestätigen, als nicht passend oder als keine verwertbare
Stimme markieren und in eine vorhandene oder neue Gruppe verschieben. Abgelehnte
Proben bleiben vom erneuten Gruppieren ausgeschlossen. Sobald Bestätigungen vorliegen,
wird der Gruppenmittelpunkt ausschließlich aus bestätigten Proben neu berechnet.

Personen werden in einem eigenen Administrationsmenü verwaltet. Profilbilder und kurze
Prüfvideos liegen ausschließlich im lokalen, geschützten Medienverzeichnis. Aus einem
angehaltenen Video kann manuell ein Profilbild übernommen werden. Die Videotonspur wird
lokal mit FFmpeg als Mono-WAV extrahiert und mit demselben Stimmabdruckverfahren gegen
bestätigte Gruppen der Person beziehungsweise ersatzweise gegen anonyme Gruppen geprüft.
Ähnlichkeitswerte sind keine Identitätswahrscheinlichkeiten und erfordern eine manuelle
Bewertung.

Mit **In Lärmüberwachung einbeziehen** lässt sich je Profil festlegen, ob bestätigte
Ereignisse in Dashboard-Kennzahlen und Belastungsbewertung einfließen. Beim Ausschluss
bleiben Ereignisse und Zuordnungen für die persönliche Ansicht erhalten. Die Einstellung
ist reversibel und verwendet eine eigene Ereignismarkierung, unabhängig von anderen
Ausblendungsgründen.

Der integrierte Scheduler startet täglich um 03:00 Uhr in `Europe/Berlin` einen nächtlichen Lauf,
sofern für den Tag noch kein Nachtlauf existiert und kein anderer Lauf aktiv ist. Die Stunde kann
mit `NIGHTLY_REVIEW_HOUR` geändert werden. Neustarts sind sicher, weil Laufstatus, Fortschritt und
Zähler in PostgreSQL bzw. SQLite persistiert sind.

## Beurteilungszeiten

Die zentrale Bewertungsfunktion verwendet die in der Roadmap gesetzten Werte:

- Tag 06:00–19:00 Uhr: 50 dB(A)
- Abend 19:00–22:00 Uhr: 35 dB(A)
- Nacht 22:00–06:00 Uhr: 35 dB(A)
- werktags +6 dB von 06:00–07:00 und 20:00–22:00 Uhr
- sonn- und bundesweite Feiertage +6 dB von 06:00–09:00, 13:00–15:00 und 20:00–22:00 Uhr

Zeitumstellungen werden über die Zeitzone `Europe/Berlin` berücksichtigt. Als Feiertage werden
die bundesweit einheitlichen gesetzlichen Feiertage inklusive der beweglichen Osterfeiertage
gewertet; landesspezifische Feiertage sind bewusst nicht pauschal enthalten.

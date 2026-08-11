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
- Ereignisse ohne gespeicherten Audioclip bleiben mit Zeit, Pegel und vorhandener Kategorie
  für Historie und Statistik erhalten. Sie tragen den Status `context_only` und sind damit
  ausdrücklich nur eine Metadaten-/Kontextwertung, kein akustischer Nachweis. Diese Einträge
  erscheinen nicht in der akustischen Prüfauswahl, werden von automatischen Prüfläufen
  übersprungen und niemals als KI-Trainingsbeispiel verwendet. Das Audio-Lab zeigt ihre Anzahl
  separat als **Ohne Clip · Kontext** an. Auch neu eingehende Ereignisse werden nur dann in die
  akustische Prüfliste aufgenommen, wenn tatsächlich ein Clip zugeordnet ist. Im Dashboard
  ersetzt der Hinweis **Ohne Aufnahme · nicht akustisch prüfbar** den Anhören-Button und die
  akustische Zuordnung.

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
Ausblendungsgründen. Administratoren und Operatoren können ein abspielbares Ereignis direkt
im Live-Ereignisstrom oder im aktuellen Lärmprotokoll einer aktiven Person zuordnen. Der
Hinweis **aus Lärmmessung ausgeschlossen** wird unmittelbar an der Zeile angezeigt; Ereignisse
ohne Aufnahme bieten diese akustisch begründete Direktzuordnung nicht an.

Für bekannte Nahbereichssituationen stehen die nicht lernenden Klassen **Normales
Gespräch/Nahbereich** und **Eigene Tätigkeit/Nahbereich** zur Verfügung. Sie beschreiben den
manuell bekannten Kontext, ohne aus dem ursprünglichen Modelllabel – insbesondere `Speech` –
eine globale Lernregel abzuleiten. Mit **Nicht bewerten** wird ein einzelnes Live-Ereignis samt
Grund aus Kennzahlen, Heatmap, Kalender und Belastungsbewertung ausgeschlossen. Im Audio-Lab
kann dieselbe Entscheidung über **Alle sichtbaren wählen** gesammelt auf längere Zeiträume
angewendet werden. Rohzeit, dB-Wert, Aufnahme, Modelllabel und Audit-Zuordnung bleiben erhalten.
**Kein Lärm / verwerfen** ist hierfür ausdrücklich nicht vorgesehen, weil diese Funktion das
Ereignis und seinen Clip löscht und nach drei gleichen Bestätigungen bereits den Modelltreffer
vor der Speicherung verwirft.

Der integrierte Scheduler startet täglich um 03:00 Uhr in `Europe/Berlin` einen nächtlichen Lauf,
sofern für den Tag noch kein Nachtlauf existiert und kein anderer Lauf aktiv ist. Die Stunde kann
mit `NIGHTLY_REVIEW_HOUR` geändert werden. Neustarts sind sicher, weil Laufstatus, Fortschritt und
Zähler in PostgreSQL bzw. SQLite persistiert sind.

Der Live-Audio-Eingang begrenzt jeden Gerätestrom auf die konfigurierte 16-kHz-Mono-Echtzeitrate
mit einem fünfsekündigen Puffer für Verbindungsabbrüche. Schneller eintreffende PCM-Pakete werden
mit `202 Accepted` quittiert, aber nicht erneut verarbeitet. Dadurch erzeugen Geräte keine
Retry-Warteschlange und Audio-Ingest kann Dashboard, Healthcheck und WebSocket nicht verdrängen.

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

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

# Lärmbewertung nach Ereignisklasse

Administratoren bearbeiten die Bewertung im Dashboard unter **Administration →
Lärmbelastung nach Klasse**. Ein Häkchen bedeutet, dass Ereignisse dieser Klasse in
Statistik, KPIs, Überschreitungsquote, Kalender und Heatmap einfließen. Ohne Häkchen
bleiben Erkennung, Aufnahme, Live-Anzeige und manuelle Klassifizierung erhalten; nur die
Lärmbewertung lässt das Ereignis aus.

Die Einstellung ist pro Kundenbereich (Tenant) getrennt. Eine Feinklasse hat Vorrang vor
ihrer Hauptkategorie. Dadurch kann beispielsweise **Fahrzeuge** insgesamt ausgeschlossen,
**Flugzeug/Fluglärm** aber gezielt einbezogen werden. Änderungen gelten sofort auch für
bereits vorhandene Ereignisse, ohne deren gespeicherte Klassifizierung umzuschreiben.

## Standardbelegung

| Hauptkategorie | Standard | Feinklassen |
|---|---|---|
| Kein Lärm / verwerfen | ausgeschlossen | – |
| Wind | ausgeschlossen | Windgeräusch (erbt den Ausschluss) |
| Umgebung/Natur | ausgeschlossen | Ländliche/natürliche Umgebung (erbt den Ausschluss) |
| Technisches Störgeräusch | ausgeschlossen | Netzbrummen, Stimmgabel/Resonanz, KI-Fehlklassifikation (erben den Ausschluss) |
| Hupen | einbezogen | Fahrzeughupen, Zughupen |
| Stimmen | einbezogen | Lautes Rufen/Geschrei, Gespräch, Streit / mehrere Personen |
| Eigene Tätigkeit/Nahbereich | einbezogen | – |
| Schlag/Aufprall/Knall | einbezogen | Fußball gegen Beton, Fußball gegen Metall, Schlagen gegen Laterne, Knallkörper |
| Musik | einbezogen | – |
| Hund | einbezogen | – |
| Motor | einbezogen | – |
| Sirene | einbezogen | Polizeisirene |
| Vögel | einbezogen | – |
| Maschinen | einbezogen | – |
| Haushalt/Alltag | einbezogen | Schritte / Fußtritte, Geschirr, Einkaufswagen / Rollen und Scheppern, Wohnungstür zuschlagen |
| Fahrzeuge | einbezogen | Pkw, Motorrad, Fahrrad, Bremsen / Reifenquietschen, Flugzeug/Fluglärm |
| Sonstiger Lärm | einbezogen | eigenständige Feinklasse ohne Hauptkategorie |

Die ersetzten, inaktiven Klassen „Normales Gespräch/Nahbereich“, „Anhaltendes Rufen“ und
„Lautes Schreien“ bleiben aus Gründen der Datenkompatibilität sichtbar, werden aber nicht
mehr für neue Zuordnungen angeboten. Auch ihre Bewertung kann für historische Datensätze
bearbeitet werden.

Zusätzlich zu den Klassenregeln bleiben ausdrückliche Ausschlüsse einzelner Ereignisse und
der Ausschluss über eine Personenzuordnung wirksam. Der Beurteilungszuschlag für
empfindliche Tageszeiten ist eine separate Einstellung.

## Flugzeug zuordnen

Ein Flugzeug wird als Hauptkategorie **Fahrzeuge** und Feinklasse
**Flugzeug/Fluglärm** zugeordnet. Ein Pkw oder Motorrad wird entsprechend als
Feinklasse **Pkw** oder **Motorrad** zugeordnet. Fahrradgeräusche werden als
**Fahrrad** bzw. **Bremsen / Reifenquietschen** zugeordnet. Schritte, Geschirr,
Einkaufswagen und eine zuschlagende Wohnungstür gehören zu
**Haushalt/Alltag**. Ob ein Fahrzeugereignis
anschließend als Lärmbelastung zählt, entscheidet allein der Schalter der
Feinklasse (oder, solange keine eigene Feinregel gespeichert ist, die
Einstellung der Hauptkategorie Fahrzeuge).

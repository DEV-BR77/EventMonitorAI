# EventMonitorAI Roadmap

Die Roadmap beschreibt die angestrebte Reihenfolge. Termine werden erst festgelegt, wenn Umfang und technische Risiken ausreichend geklärt sind.

## Phase 0 – Repository und Grundlagen

- [x] zentrale Projektstruktur
- [x] Architektur- und Entscheidungsdokumentation
- [x] Coding Guidelines und Contribution-Prozess
- [x] CI-Grundprüfung
- [x] Release-Workflow für saubere Quellcodepakete
- [x] einheitliche Versionierung aller Komponenten
- [x] reproduzierbare Entwicklungsumgebung

## Phase 1 – Stabile Ereigniserfassung

- [x] ESP32-S3 sendet Audio per UDP
- [x] Raspberry Pi verarbeitet Audiofenster
- [x] YAMNet-Klassifikation als Ausgangspunkt
- [x] FastAPI-Backend und Ereignisdatenbank
- [x] robuste Wiederverbindung und Paketverlustbehandlung
- [x] Geräteidentität, Health-Status und Telemetrie
- [x] nachvollziehbare Audiopegel-Kalibrierung über Dashboard mehrere Mikrofone gleichzeitig mit Angabe Referenzwert bei leisem mittleren und lauten Pegel

## Phase 2 – EventMonitor AudioLab

- [x] ZIP- und Ordnerimport
- [x] Dublettenprüfung
- [x] Audio-/dB-Segmentierung
- [x] manuelles Labeling und CSV-Export
- [x] Importprotokoll und Wiederaufnahme abgebrochener Imports
- [x] interaktiver dB-Verlauf, Spektrogramm und Segmentnavigation
- [x] variable Segmentgrenzen und Ereigniszuschnitt
- [x] Backup und Datenmigration

## Phase 3 – Lernende Klassifizierung

- [x] versionierte Feature- und Preprocessing-Pipeline
- [x] Trainings-, Validierungs- und Testaufteilung nach Aufnahmen
- [x] Basismodell und nachvollziehbare Qualitätsmetriken
- [x] Modellvorschläge mit Bestätigung/Korrektur
- [x] Active Learning für unsichere oder informative Beispiele
- [x] Audio-Embeddings und Ähnlichkeitssuche
- [x] Personen durch Lärm wie schreien, rufen identifizieren und klassifizieren - neue Personen anlegen die editierbar sind mit frei gewählten Namen - gesonderte Statistik je Personen, Beurteilungszeit, Lärmkategorie und Häufigkeit
- [x] anonyme automatische Stimmgruppierung vorhandener Aufnahmen als Person 1, Person 2 usw. mit späterer Umbenennung und Verknüpfung zu bestätigten Personenprofilen
- [x] lokale Modellverwaltung und Rollback

## Phase 4 – Ereignisse und Cases

- [x] einzelne Segmente zu zusammenhängenden Ereignissen verbinden
- [x] Schreien, Rufen und Impulse zeitlich gruppieren
- [x] Case-Modell mit Beginn, Ende, Dauer und Teilereignissen
- [x] Notizen, Bestätigungsstatus und revisionssichere Änderungshistorie
- [x] Lärmprotokoll als CSV und PDF
- [x] Ringpuffer im PSRAM
    2 Sekunden Audio vor dem Ereignis mit speichern
    Ereignistrigger
    WAV-Clip an den Pi übertragen

## Phase 5 – Dashboard und Integration

- [x] Kalender, Timeline, Heatmaps und Statistiken
- [x] globaler Filter für einzelne Kalendertage und frei wählbare Von-bis-Zeiträume
- [x] gesonderte KPI-Seite mit Überschreitungsquote, P95-Pegel, Lärmdauer, Tageszeiten, Arten- und Gerätevergleich
- [x] Live-Ereignisansicht
- [x] Home-Assistant-Integration
- [x] Benachrichtigungsregeln
- [x] PostgreSQL-Option und Mehrgerätebetrieb
- [x] Rollen, Authentifizierung und Zugriffsschutz
- [x] Öffentliche Selbstregistrierung mit E-Mail-Adresse, 24 Stunden gültigem
      Bestätigungslink, Login-Freigabe erst nach Bestätigung, eigenem mandantenisoliertem
      Kundenbereich und sichtbarer Administrator-Benachrichtigung

## Phase 6 – Dashboard Erweiterungen

  - [x] Mikrofon Verwaltung - Namen, Position, Aktiv/Inaktiv, Kalibrierung
  - [x] Live-Soundausgabe je Mikrofon anwählbar und pro User durch Admin freizugeben, ohne Freigabe Funktion nicht sichtbar beim User
  - [x] Karte Bild für Positionierung der Mikrofone und Darstellung von Messergebnissen ![Messbereich](image-1.png) Die Mikrofone sollen auf dem Bild positioniert werden und Messergebnisse und Anzahl Überschreitungen darstellen, zusäzlich Erstellung einer Heatmap der Schallpegelausbreitung
- [x] Bereitstellung einer Progressive Web App mit Pushnachrichten bei Lärmereignissen mit Bestätigung oder Ablehnungsbutton als Antwort - Antwort mit Angabe User, Ereignis ID speichern und als Zeuge in Lärmprotokoll einbinden
- [x] Darstellung der letzten 5 Ereignisse
- [x] fortlaufende identische Detektionen je Mikrofon zu einem Ereignis mit Start, Ende und Dauer zusammenführen
- [x] Rollen, Authentifizierung und Zugriffsschutz

## Phase 7 - KI

- [x] Mehrquellen- und Nebenklassifizierung als nächste KI-Erweiterung umsetzen:
      dominante Geräuschquelle weiterhin als Hauptklasse speichern, gleichzeitig hörbare
      Quellen als eine oder mehrere Nebenklassen erfassen und im Live-Strom, Audio-Lab sowie
      Lärmprotokoll getrennt darstellen. Beispiel: Hauptklasse „Schlagen gegen Metallpfosten“,
      Nebenklasse „Lautes Rufen/Geschrei“.
- [x] Gemischte Aufnahmen standardmäßig nicht als eindeutiges Lernbeispiel verwenden. Für jede
      Haupt- und Nebenklasse muss eine getrennte manuelle Lernfreigabe möglich sein; bestehende
      Lernregeln und historische Einzelklassifizierungen bleiben kompatibel.
- [x] Datenmodell, API und Mandantenfilter für mehrere Klassenzuordnungen je Ereignis ergänzen,
      inklusive Auditverlauf, Korrektur und Entfernung einzelner Nebenklassen.
- [x] Mehrquellen-Klassifizierung mit Backend-, Frontend-, Mandanten- und Regressionstests
      sowie Bedien- und Datenschutzdokumentation abschließen, bevor diese Punkte erledigt werden.

Gilt für die Live Analyse wie Audi-Lab

Ein Modell wie YAMNet kann allgemeine Klassen erkennen, zum Beispiel:
Schreien oder Rufen
Autohupe
Hund
Musik
Motor
Sirene
Schlag- oder Aufprallgeräusch
Menschenmenge

Zusätzlich manuell und dadurch erlernte Klassen wie:

Fußball gegen Betonwand
Fußball gegen Metallhütte
Schlagen gegen Laternen
konkrete Art des Aufpralls

Dafür eigene Beispiele sammeln und einen Klassifikator nachtrainieren.
Eine Verwaltung für das Pflegen von Klassen im Dashboard Administrator-Einrichtung bereitstellen
Im Protokoll würden wir zunächst beispielsweise speichern:
Primärklasse: Impact / Schlaggeräusch
Sicherheit: 91 %
Unterklasse: Fußball gegen Metall
Status: manuell zugeordnet
Durch die Bestätigungen bauen wir gleichzeitig Trainingsdaten für die spätere automatische Unterklasse auf.
manuelle Korrektur für das Lärmprotokoll

Wir bauen zum Start zwei Ebenen:

1. Automatische Basisklasse
    Hupen
    Rufen/Schreien
    Schlag/Aufprall/Knall
    Musik
    Hund
    Motor
    Sirene
    Vögel
    Maschinen
    Fahrzeuge
2. Manuelle Feinzuordnung
    Fußball gegen Beton
    Fußball gegen Metall
    Schlagen gegen Laterne
    Knallkörper
    anhaltendes Rufen
    lautes Schreien
    Streit / mehrere Personen
    Fahrzeughupen
    sonstiger Lärm
So bekommst du früh ein brauchbares Lärmprotokoll, ohne dass wir dir falsche Präzision vortäuschen.

## Phase 8 – ## Audio-Lab

**Umsetzungsstatus: abgeschlossen**

- [x] Audio-Lab in das geschützte Dashboard eingebunden
- [x] Klassenkacheln, Statuszählung und Sammelbestätigung
- [x] Automatische und nächtliche Prüfläufe
- [x] Unterbrechung und Fortsetzung mit persistentem Fortschritt
- [x] Beurteilungszeiten, Zuschläge und Referenzwerte zentral umgesetzt und getestet
- [x] Phase-8-Abnahme: deutsche Kategorien, Tagesfilter und navigierbarer Kalender mit
      beschrifteten Aktivitäts- und Überschreitungswerten
- [x] Phase-8-Abnahme: Wiedergabe und automatische Einzelauswahl in Übersicht,
      Live-Ereignisstrom und Sammelprüfung; Filter „nur mit Aufnahme“
- [x] Phase-8-Abnahme: serverseitiger Fünf-Sekunden-Audiopuffer als Rückfallebene für
      Ereignisclips, unabhängig vom ESP-Ereignisschwellwert
- [x] Phase-8-Abnahme: historischer WAV-, CSV- und ZIP-Import im geschützten Dashboard
- [x] Phase-8-Abnahme: Personenprofile, bestätigte Zuordnung und Häufigkeitsdarstellung
- [x] Phase-8-Abnahme: konfigurierbarer 6-dB-Zuschlag, Live-Bewertung standardmäßig ohne
      Zuschlag, sowie Zeitstempel für Gerätestatus
- [x] Phase-8-Abnahme: mobile Navigation und Bedienoberflächen ohne horizontales
      Seitenscrolling bei 390 Pixeln Breite
- [x] Phase-8-Nachbesserung: CSV-Referenzzeitreihen mit Zeitabgleich, prüfbarer
      Offset-Aktivierung und Anwendung auf neue Telemetrie- und Ereignispegel
- [x] Phase-8-Nachbesserung: lernfähige Wind-, Umgebungs- und technische Klassen,
      standardmäßige Ausblendung sowie datensparsame Aktion „Kein Lärm / verwerfen“
- [x] Phase-8-Nachbesserung: dauerhaft prüfbare anonyme Stimmgruppen mit Wiedergabe,
      Bestätigung, Ausschluss, Verschieben und Neuberechnung aus bestätigten Proben
- [x] Phase-8-Nachbesserung: administrative Personenprofile mit Name, Profilbild,
      geschütztem Prüfvideo, manuell übernehmbarem Videoframe und Vergleich der
      extrahierten Videotonspur mit bestätigten beziehungsweise anonymen Stimmgruppen
- [x] Phase-8-Nachbesserung: Personen können reversibel von Lärmkennzahlen und
      Belastungsbewertung ausgenommen werden, ohne ihre persönlichen Ereignisse zu löschen
- [x] Phase-8-Nachbesserung: akustische Klasse „Stimmen“ mit Gespräch, lautem
      Rufen/Geschrei und Streit als getrennten Feinzuordnungen sowie eine manuell startbare,
      lokale ECAPA-TDNN-Stimmgruppierung in einem ressourcenbegrenzten Hintergrund-Worker
      mit sichtbarem Fortschritt bei ununterbrochener Audioannahme

https://github.com/DEV-BR77/EventMonitorAI/tree/main/tools/audio-lab

Mit in Dashboard einbinden
Klassen per Kacheln direkt auswählbar für die Zuweisung und Bestätigung
Darstellung Anzahl offener und erledigter Ereignisse gegliedert nach unbekannt oder erkannter Klasse durch die KI
Prüfung und Bestätigung je Klasse durchführbar um in einem Rutsch identische Klassen zu bestätigen
Automatisierte Überprüfungsläufe um neue Zuweisungen für das Erlernen und zuweisen zu nutzen
Nächtlicher Prüflauf um bereits bestätigte Ereignisse zu verbessern oder die Personenerkennung zu überarbeiten.
Unterbrechung und Fortsetzung von den Überarbeitungen

## Gliederung der Beurteilungszeiten, Zuschläge und Referenzwerte

- Die Immissionsrichtwerte und Zeiten:

    1. Tag 50 dB(A)

        06.00 – 13.00 Uhr
        15:00 - 19:00 Uhr

    2. Abend 35 dB(A)

        19.00 – 22.00 Uhr

    3. Nacht 35 dB(A)

        22.00 – 06.00 Uhr

- Zuschlag für Tageszeiten mit erhöhter Empfindlichkeit

    Für folgende Zeiten ist bei der Ermittlung des Beurteilungspegels die erhöhte Störwirkung von Geräuschen durch einen Zuschlag von 6 dB zu berücksichtigen:

    1. an Werktagen

        06.00 – 07.00 Uhr
        20.00 – 22.00 Uhr

    2. an Sonn- und Feiertagen

        06.00 – 09.00 Uhr
        13.00 – 15.00 Uhr
        20.00 – 22.00 Uhr

## Phase 9 - Produktreife

- [x] Installationspakete und Upgrade-Strategie
- [x] automatisierte Backups und Aufbewahrungsregeln
- [x] Performance- und Langzeittests
- [x] Security- und Datenschutzreview
- [x] dokumentierte Release-Kriterien für v1.0

    Abnahme am 9. August 2026: 92 automatisierte Tests, reproduzierbares
    Release-Paket mit SHA-256-Prüfsumme, Docker-Neuinstallation, tägliches
    PostgreSQL-/Clip-Backup mit Aufbewahrung sowie erfolgreiche
    Wiederherstellung in einer isolierten Testdatenbank. Der öffentliche
    Lasttest verarbeitete 6.776 Anfragen in 30 Sekunden ohne Fehler bei
    100,10 ms p95. Sicherheitsheader, Zugriffsschutz, Login-Drosselung,
    Datenschutzreview und verbindliche v1.0-Freigabekriterien sind
    dokumentiert und automatisiert geprüft.

## Phase 10 - Kundenbetrieb und Vermarktungsgrundlage

- [x] technisch getrennte Kundenbereiche für Ereignisse, Audio, Geräte, KI-Daten und Auswertungen
- [x] Rollen je Kundenbereich getrennt von Tarif und Abonnementstatus
- [x] eigener Kundenbereich mit persönlichen KPIs, Geräten, Einstellungen und Lärmprotokollen
- [x] Geräteobergrenzen und Aufbewahrungszeit je Abonnement
- [x] widerrufbare, gerätebezogene Zugangsdaten für verschlüsselten Internet-Ingest
- [x] Plattformverwaltung zum Anlegen von Kundenbereichen und Erstadministratoren
- [ ] produktiver Zahlungsanbieter mit Webhooks, Rechnungsstatus und Kündigungsablauf
- [ ] juristisch geprüfte Vertrags-, Datenschutz- und Auftragsverarbeitungsunterlagen
- [ ] echte Quell-IP-Netzerkennung für die öffentliche Website: Caddy entweder nativ
      unter Windows betreiben oder einen vorgeschalteten, vertrauenswürdigen Proxy
      einsetzen; Client-IP-Header nur aus explizit konfigurierten Proxy-Netzen
      akzeptieren, Datenschutz und Aufbewahrungsdauer dokumentieren sowie die
      Erkennung mit externen Zugriffen testen

## Phase 11 - EventMonitor Voice für Android und iOS

- [ ] öffentliches Interessen- und späteres Selbstregistrierungsverfahren für
      persönliche Kundenbereiche
- [ ] Tarifmodell für eine geliehene, vorkonfigurierte Messstelle sowie für die
      Nutzung eines eigenen Smartphones ohne Leihgerät
- [ ] gemeinsame mobile Codebasis für Android und iOS mit Anmeldung,
      Gerätezuordnung, Mikrofonfreigabe und verständlicher Datenschutzinformation
- [ ] lokale, kalibrierbare Schallpegelmessung mit dokumentierter Geräteabweichung;
      Smartphone-Werte nicht ungeprüft mit einer Referenzmessstelle gleichsetzen
- [ ] energiesparende Ereigniserkennung und ausdrücklich gestartete Messsitzungen;
      Einschränkungen der Hintergrundaufnahme unter Android und iOS berücksichtigen
- [ ] verschlüsselte Übertragung von Pegelwerten und freigegebenen Ereignisdaten an
      den jeweiligen Kundenbereich über widerrufbare Gerätezugangsdaten
- [ ] persönliche Live-Ansicht, KPIs, Ereignisprüfung, Push-Benachrichtigungen und
      Export des eigenen Lärmprotokolls in der App
- [ ] Einwilligungs-, Lösch-, Aufbewahrungs- und Berechtigungskonzept für mobile
      Mikrofon- und Ereignisdaten einschließlich transparenter Aufnahmeanzeige
- [ ] Beta-Test auf realen Android- und iPhone-Geräten, Sicherheitsprüfung sowie
      Veröffentlichungsvorbereitung für Google Play und Apple App Store

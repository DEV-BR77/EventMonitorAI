# Datenschutz und Datenhaltung

EventMonitorAI verarbeitet potenziell sensible Audio- und Ereignisdaten. Die Architektur folgt deshalb dem Prinzip **Local First**.

## Datenklassen

1. Rohaufnahmen und importierte Messpakete
2. dB- und Frequenzmesswerte
3. automatisch erzeugte Segmente
4. Modellvorhersagen
5. menschlich bestätigte Labels und Notizen
6. trainierte Modelle und Embeddings
7. optional hinterlegte Personenbilder, kurze Prüfvideos und daraus extrahierte Stimmproben

## Grundregeln

- Daten bleiben standardmäßig auf dem lokalen System.
- Es erfolgt kein Cloud-Upload ohne explizite Konfiguration.
- Aufbewahrungsfristen und automatische Löschung sollen konfigurierbar werden.
- Exporte müssen bewusst ausgelöst werden.
- Audio, Datenbanken und Modelle werden nicht in Git gespeichert.
- Zugriff auf Gerät, Dateisystem und Backups muss geschützt werden.
- Personenbilder, Prüfvideos und extrahierte Videotonspuren bleiben im lokalen
  Medienverzeichnis und sind über das Dashboard ausschließlich für Administratoren
  abrufbar. Ein Videoimport oder Profilbild muss bewusst ausgelöst werden.
- Live-Audio wird für die Wiedergabe flüchtig übertragen. Das Backend hält pro Mikrofon einen
  flüchtigen 20-Sekunden-Ringpuffer und persistiert daraus nur bei einem Ereignis einen
  höchstens zehn Sekunden langen, um den lautesten Ausschlag ausgerichteten geschützten Clip.
  Sichtbar und abrufbar ist Live-Audio ausschließlich für vom Administrator pro Mikrofon
  freigegebene Benutzer.
- Als **Kein Lärm** verworfene Ereignisse und ihre Clips werden gelöscht. Für das automatische
  Verwerfen bleibt nur das normalisierte Modelllabel mit einem Bestätigungszähler erhalten;
  Uhrzeit, Pegel, Gerät und Audio werden nicht in diesem Lernmuster gespeichert.
- Push-Abonnements werden dem angemeldeten Benutzer zugeordnet. Eine Bestätigung oder Ablehnung
  wird mit Benutzername, Ereignis-ID und Zeitstempel als Zeugenreaktion im Lärmprotokoll geführt;
  Antwortlinks sind signiert und laufen nach 24 Stunden ab.

## Aussagegrenzen

Eine akustische Klassifikation beschreibt ein Muster wie „Schreien“, „Rufen“ oder „Aufprall“. Sie beweist weder die Identität einer Person noch sicher die konkrete Ursache. Berichte sollten automatische und bestätigte Bewertungen klar unterscheiden.
Auch eine hohe Stimmgruppenähnlichkeit ist keine Identitätswahrscheinlichkeit. Die
Zuordnung eines Bildes, Videos, Namens oder Stimmprofils bleibt eine manuelle Bewertung.

## Rechtlicher Hinweis

Die Zulässigkeit von Audioaufnahmen hängt vom Einsatzort, Aufnahmeumfang und geltenden Recht ab. Vor einem dauerhaften oder fremde Personen betreffenden Einsatz ist eine eigenständige rechtliche Prüfung erforderlich.

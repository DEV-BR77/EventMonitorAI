# Datenschutz und Datenhaltung

EventMonitorAI verarbeitet potenziell sensible Audio- und Ereignisdaten. Die Architektur folgt deshalb dem Prinzip **Local First**.

## Datenklassen

1. Rohaufnahmen und importierte Messpakete
2. dB- und Frequenzmesswerte
3. automatisch erzeugte Segmente
4. Modellvorhersagen
5. menschlich bestätigte Labels und Notizen
6. trainierte Modelle und Embeddings

## Grundregeln

- Daten bleiben standardmäßig auf dem lokalen System.
- Es erfolgt kein Cloud-Upload ohne explizite Konfiguration.
- Aufbewahrungsfristen und automatische Löschung sollen konfigurierbar werden.
- Exporte müssen bewusst ausgelöst werden.
- Audio, Datenbanken und Modelle werden nicht in Git gespeichert.
- Zugriff auf Gerät, Dateisystem und Backups muss geschützt werden.

## Aussagegrenzen

Eine akustische Klassifikation beschreibt ein Muster wie „Schreien“, „Rufen“ oder „Aufprall“. Sie beweist weder die Identität einer Person noch sicher die konkrete Ursache. Berichte sollten automatische und bestätigte Bewertungen klar unterscheiden.

## Rechtlicher Hinweis

Die Zulässigkeit von Audioaufnahmen hängt vom Einsatzort, Aufnahmeumfang und geltenden Recht ab. Vor einem dauerhaften oder fremde Personen betreffenden Einsatz ist eine eigenständige rechtliche Prüfung erforderlich.

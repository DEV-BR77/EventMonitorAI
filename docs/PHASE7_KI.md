# Phase 7 – zweistufige KI-Klassifikation

EventMonitorAI trennt bewusst zwischen der allgemeinen Modellerkennung und einer manuell
bestätigten Feinzuordnung:

1. Die Live-Analyse ordnet bekannte YAMNet-Ergebnisse einer administrierbaren Basisklasse zu.
2. Operatoren und Administratoren können im Dashboard eine passende Feinzuordnung auswählen.
3. Jede manuelle Änderung benötigt eine Begründung und wird als eigener Revisionsdatensatz mit
   Benutzer und Zeitstempel erhalten.
4. AudioLab synchronisiert denselben Klassenkatalog. Beim Labeln werden Basiscode, optionaler
   Feincode und der Status `manual` gespeichert.
5. Für das Training verwendet AudioLab weiterhin das bestätigte sichtbare Label. Bei vorhandener
   Feinzuordnung ist dies die Feinklasse, ansonsten die Basisklasse.
6. Der Raspberry Pi überträgt ausgelöste WAV-Clips zusätzlich authentifiziert an das Dashboard.
   Das Backend prüft Format und SHA-256, speichert sie in einem separaten persistenten
   Docker-Datenträger und ordnet sie zeitnahen Ereignissen desselben Geräts zu.
7. AudioLab kann ausschließlich manuell bestätigte Ereignisse mit Feinzuordnung importieren.
   Beim Import werden Hash und Audioformat erneut geprüft; bereits vorhandene Beispiele werden
   nicht dupliziert.

Deaktivierte Klassen bleiben in vorhandenen Datensätzen erhalten, werden aber nicht mehr für neue
Zuordnungen angeboten. Eine unbekannte allgemeine Modellerkennung erhält keine erfundene
Basisklasse; die Zuordnung bleibt leer, bis sie geprüft wurde.

Das Lärmprotokoll enthält neben der sichtbaren Kategorie auch Primärklassen-Code,
Unterklassen-Code und Zuordnungsstatus. Die unveränderte ursprüngliche Modellerkennung und deren
Konfidenz bleiben parallel erhalten.

## Betriebliche Trennung

Die Clip-Übertragung nutzt denselben Ingest-API-Schlüssel wie die Ereignisübertragung. Der
geschützte Trainingsdaten-Abruf erfordert dagegen eine Anmeldung als Operator oder Administrator.
AudioLab speichert die dabei verwendeten Zugangsdaten nicht. Originalclips auf dem Pi bleiben
erhalten; ein fehlgeschlagener Dashboard-Transfer blockiert weder ESP32 noch lokale Erfassung.

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

Deaktivierte Klassen bleiben in vorhandenen Datensätzen erhalten, werden aber nicht mehr für neue
Zuordnungen angeboten. Eine unbekannte allgemeine Modellerkennung erhält keine erfundene
Basisklasse; die Zuordnung bleibt leer, bis sie geprüft wurde.

Das Lärmprotokoll enthält neben der sichtbaren Kategorie auch Primärklassen-Code,
Unterklassen-Code und Zuordnungsstatus. Die unveränderte ursprüngliche Modellerkennung und deren
Konfidenz bleiben parallel erhalten.

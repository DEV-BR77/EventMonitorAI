# AudioLab 2.0

## Vision

AudioLab entwickelt sich von einem internen Import- und Labeling-Werkzeug zu einer eigenständigen Open-Source-Plattform für die professionelle Verwaltung, Annotation und Aufbereitung von Audiodaten für KI-Modelle.

## Zielbild

AudioLab soll für Audio eine vergleichbare Rolle übernehmen wie spezialisierte Annotationstools für Bild- und Videodaten.

## Funktionsbereiche

### Projektverwaltung

- mehrere Projekte verwalten
- mehrere Aufnahmen je Projekt
- Projektstatus und Fortschritt
- Audiozeit, Ereignisse und Labels auswerten

### Label Management

- eigene Labels und Kategorien
- Beschreibungen und Tastenkürzel
- optionale Farben
- Qualitätsstatus wie unsicher, prüfen oder verwerfen

### Professionelles Labeling

- automatischer Wechsel zum nächsten Ereignis
- Tastaturmodus
- Vor- und Zurücknavigation
- Undo und Redo
- Batch Labeling
- Mehrfachauswahl

### Audioanalyse

- Wellenform
- Spektrogramm
- Zoom und Marker
- Wiedergabegeschwindigkeit
- Loop-Wiedergabe
- Lautstärkeregelung
- Vergleich mehrerer Ereignisse

### Filter und Suche

Filter nach:

- Label
- Konfidenz
- Datum und Uhrzeit
- Lautstärke
- Dauer
- Quelle
- Projekt
- Klassifizierungsstatus

### KI-Unterstützung

- Anzeige mehrerer Modellvorschläge
- Konfidenzwerte
- Vorschlag mit einem Klick übernehmen
- unsichere Fälle priorisieren
- Active Learning vorbereiten

### Qualitätskontrolle

- Review-Status
- Kommentare
- Freigaben
- Änderungshistorie
- Vergleich zwischen Annotatoren

### Teammodus

- mehrere Benutzer
- Rollen und Berechtigungen
- Reviewer-Workflow
- nachvollziehbare Änderungen

### Dataset Export

Geplante Exportformate und Ziele:

- CSV
- Parquet
- TensorFlow
- PyTorch
- ONNX
- YAMNet
- BirdNET
- benutzerdefinierte Trainingspipelines

### Modell- und Plugin-System

Langfristige Unterstützung für:

- YAMNet
- BirdNET
- Whisper
- TensorFlow-Modelle
- PyTorch-Modelle
- eigene Plugins

## Langfristige Einsatzbereiche

- Umweltgeräusche
- Lärmprotokollierung
- Bioakustik
- industrielle Geräuschanalyse
- Smart Home
- Sicherheits- und Ereigniserkennung
- Forschung und Dataset-Erstellung

## Perspektive AudioLab 3.0

AudioLab soll aus bestätigten Labels lernen und neue Ereignisse automatisch vorsortieren. Der Benutzer bewertet dann bevorzugt unsichere oder neue Geräuschklassen.
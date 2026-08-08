# Audio-Embeddings und Ähnlichkeitssuche

AudioLab bildet jedes Segment in einen modellgebundenen Embedding-Vektor ab. Als
stabile Ausgangsrepräsentation dienen die versionierten Log-Mel- und
Spektralfeatures. Der beim Basismodell gelernte Scaler überführt sie in denselben
Merkmalsraum; anschließend werden die Vektoren L2-normalisiert.

Gespeichert werden Modellname, Feature-Pipeline-Fingerprint, Dimension,
Erstellungszeit und der kompakte Float32-Vektor. Die Suche vergleicht nur
Embeddings desselben Modells und derselben Pipeline mittels Cosinus-Ähnlichkeit.
Damit werden inkompatible Repräsentationen nicht vermischt.

Unter **Modelltraining** lassen sich Embeddings neu berechnen. In **Ereignisse
lernen** erscheinen anschließend die fünf ähnlichsten anderen Segmente mit
Aufnahme, Zeitbereich, vorhandenem Label und Ähnlichkeitswert. Das unterstützt
Konsistenzprüfungen und das schnelle Finden wiederkehrender Geräusche.

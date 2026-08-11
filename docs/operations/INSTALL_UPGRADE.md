# Installation und Upgrade

## Unterstützter Produktionsweg

Der unterstützte Produktionsweg ist Docker Compose mit PostgreSQL. Auf Windows
10/11 wird Docker Desktop benötigt. Nach dem Klonen genügt:

```powershell
.\scripts\install.ps1 -Build
```

Das Skript prüft Docker, erzeugt bei der ersten Installation eine lokale
`.env.docker` mit kryptografisch zufälligem Datenbankpasswort, Auth-Schlüssel
und Ingest-Schlüssel, startet alle Dienste und wartet auf den Health-Check.
Vorhandene Geheimnisse werden niemals überschrieben.

## Upgrade

```powershell
.\scripts\upgrade.ps1 -Branch main
```

Ein Upgrade wird bei lokalen Git-Änderungen verweigert. Vor dem `ff-only`-
Update wird ein vollständiges Backup erstellt und das bisherige Containerimage
als `eventmonitorai-app:rollback-<Zeitstempel>` markiert. Danach werden Image,
Schema und Dienste aktualisiert und der Health-Check ausgeführt.

Die derzeitigen Schemaänderungen sind ausschließlich additiv. Ein
Anwendungsrollback kann das markierte Image verwenden. Ein Datenrollback muss
über das automatisch angelegte Vor-Upgrade-Backup erfolgen; dabei gehen alle
nach diesem Backup entstandenen Daten verloren.

## Releasepakete

Tags im Format `vMAJOR.MINOR.PATCH` erzeugen automatisch:

- ein geprüftes, geheimnisfreies ZIP-Installationspaket,
- ein SHA-256-Manifest,
- ein versioniertes OCI-Image in GitHub Container Registry.

Das ZIP enthält weder `.env`, Datenbanken, Audio, Modelle noch Exporte.

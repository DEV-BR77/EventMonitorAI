# Backup, Aufbewahrung und Wiederherstellung

Der Compose-Dienst `backup` erzeugt unmittelbar nach seinem Start und danach
standardmäßig alle 24 Stunden ein konsistentes PostgreSQL-Custom-Format-Dump,
ein komprimiertes Cliparchiv und SHA-256-Prüfsummen unter `backups/`.

Konfiguration in `.env.docker`:

```dotenv
BACKUP_INTERVAL_SECONDS=86400
BACKUP_RETENTION_DAYS=30
```

Backups werden mit restriktiver Prozess-Umask erstellt. Der Hostordner muss
zusätzlich durch Windows-/Linux-Dateirechte geschützt und in die reguläre
Datenträgersicherung aufgenommen werden. Backups enthalten sensible Audio- und
Kontodaten und dürfen nicht in Git oder unverschlüsselte Cloudspeicher gelangen.

## Manuelles Backup

```powershell
.\scripts\backup.ps1 -Label vor-konfigurationsaenderung -RetentionDays 30
```

Das manuelle Format enthält außerdem ein JSON-Manifest mit Dateigrößen und
SHA-256-Werten.

## Wiederherstellung

```powershell
.\scripts\restore.ps1 -BackupDirectory .\backups\20260809T040000Z
# Nach Prüfung des Pfades:
.\scripts\restore.ps1 -BackupDirectory .\backups\20260809T040000Z -Force
```

Die Wiederherstellung akzeptiert ausschließlich Verzeichnisse unter dem
Projektordner `backups`, stoppt schreibende Dienste, ersetzt Datenbank und
Clipbestand und startet anschließend App und Backupdienst neu. Sie ist bewusst
nicht automatisch reversibel; vor jedem Restore ist das aktuelle System erneut
zu sichern.

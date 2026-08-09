param(
    [Parameter(Mandatory=$true)][string]$BackupDirectory,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backup = (Resolve-Path -LiteralPath $BackupDirectory).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $root "backups")).Path
if (-not $backup.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar)) { throw "Backup muss unter $allowedRoot liegen." }
if (-not (Test-Path -LiteralPath (Join-Path $backup "database.dump"))) { throw "database.dump fehlt." }
if (-not (Test-Path -LiteralPath (Join-Path $backup "manifest.json"))) { throw "manifest.json fehlt." }
$manifest = Get-Content -LiteralPath (Join-Path $backup "manifest.json") -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $candidate = Join-Path $backup $entry.path
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw "Backup-Datei fehlt: $($entry.path)" }
    $resolvedCandidate = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $resolvedCandidate.StartsWith($backup + [IO.Path]::DirectorySeparatorChar)) { throw "Ungültiger Manifestpfad: $($entry.path)" }
    $actualHash = (Get-FileHash -LiteralPath $resolvedCandidate -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne [string]$entry.sha256) { throw "Prüfsumme stimmt nicht: $($entry.path)" }
}
if (-not $Force) { throw "Wiederherstellung überschreibt aktuelle Messdaten. Nach Prüfung mit -Force erneut ausführen." }

Set-Location $root
docker compose --env-file .env.docker stop app backup
if ($LASTEXITCODE -ne 0) { throw "Dienste konnten nicht angehalten werden." }
docker cp (Join-Path $backup "database.dump") "eventmonitorai-postgres-1:/tmp/restore.dump"
if ($LASTEXITCODE -ne 0) { throw "Datenbank-Dump konnte nicht kopiert werden." }
docker compose --env-file .env.docker exec -T postgres pg_restore -U eventmonitor -d eventmonitor --clean --if-exists --no-owner --exit-on-error /tmp/restore.dump
if ($LASTEXITCODE -ne 0) { throw "Datenbank-Wiederherstellung fehlgeschlagen; Dienste bleiben angehalten." }
docker run --rm -v eventmonitorai_eventmonitor_clips_data:/data/clips eventmonitorai-app sh -c "find /data/clips -maxdepth 1 -type f -name '*.wav' -delete"
if ($LASTEXITCODE -ne 0) { throw "Clip-Ziel konnte nicht geleert werden; Dienste bleiben angehalten." }
if (Test-Path -LiteralPath (Join-Path $backup "clips")) { docker cp (Join-Path $backup "clips\.") "eventmonitorai-app-1:/data/clips" }
if ($LASTEXITCODE -ne 0) { throw "Clips konnten nicht wiederhergestellt werden; Dienste bleiben angehalten." }
docker compose --env-file .env.docker up -d app backup
if ($LASTEXITCODE -ne 0) { throw "Dienste konnten nach der Wiederherstellung nicht gestartet werden." }
Write-Host "Wiederherstellung abgeschlossen: $backup"

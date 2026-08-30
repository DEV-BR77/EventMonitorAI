param(
    [string]$Label = (Get-Date -Format "yyyyMMdd-HHmmss"),
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
if ($Label -notmatch '^[A-Za-z0-9._-]+$') { throw "Ungültiges Backup-Label." }
$target = Join-Path $root "backups\$Label"
if (Test-Path -LiteralPath $target) { throw "Backup-Ziel existiert bereits: $target" }
New-Item -ItemType Directory -Path $target -Force | Out-Null

docker compose --env-file .env.docker exec -T postgres pg_dump -U eventmonitor -d eventmonitor -Fc -f "/tmp/$Label.dump"
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL-Backup fehlgeschlagen." }
docker cp "eventmonitorai-postgres-1:/tmp/$Label.dump" (Join-Path $target "database.dump")
if ($LASTEXITCODE -ne 0) { throw "Datenbank-Dump konnte nicht kopiert werden." }
docker cp "eventmonitorai-app-1:/data/clips" (Join-Path $target "clips")
if ($LASTEXITCODE -ne 0) { throw "Clip-Backup konnte nicht kopiert werden." }
docker cp "eventmonitorai-app-1:/data/documentation" (Join-Path $target "documentation")
if ($LASTEXITCODE -ne 0) { throw "Dokumentations-Backup konnte nicht kopiert werden." }
$files = Get-ChildItem -LiteralPath $target -Recurse -File
$manifest = [ordered]@{
    format = 1
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    database = "database.dump"
    clip_count = @($files | Where-Object Extension -eq ".wav").Count
    documentation_count = @($files | Where-Object { $_.FullName.StartsWith((Join-Path $target "documentation")) }).Count
    files = @($files | ForEach-Object {
        [ordered]@{ path = $_.FullName.Substring($target.Length + 1); bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
}
[IO.File]::WriteAllText((Join-Path $target "manifest.json"), ($manifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem (Join-Path $root "backups") -Directory | Where-Object { $_.LastWriteTime -lt $cutoff -and $_.FullName -ne $target } | Remove-Item -Recurse -Force
Write-Host "Backup erstellt: $target"

param(
    [string]$Branch = "main",
    [switch]$SkipPull
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
if (-not (Test-Path -LiteralPath ".env.docker")) { throw ".env.docker fehlt. Zuerst install.ps1 ausführen." }
if ((git status --porcelain).Count -gt 0) { throw "Arbeitsverzeichnis enthält Änderungen; Upgrade abgebrochen." }

$previousCommit = (git rev-parse HEAD).Trim()
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
& (Join-Path $PSScriptRoot "backup.ps1") -Label "pre-upgrade-$stamp"
if (-not $SkipPull) {
    git fetch origin $Branch
    git merge --ff-only "origin/$Branch"
}

docker tag eventmonitorai-app:latest "eventmonitorai-app:rollback-$stamp" 2>$null
docker compose --env-file .env.docker build --pull app
docker compose --env-file .env.docker up -d
try {
    & (Join-Path $PSScriptRoot "install.ps1")
} catch {
    Write-Error "Upgrade fehlgeschlagen. Sicherung: backups\pre-upgrade-$stamp; vorheriger Commit: $previousCommit; Rollback-Image: eventmonitorai-app:rollback-$stamp"
    throw
}
Write-Host "Upgrade von $previousCommit auf $((git rev-parse HEAD).Trim()) abgeschlossen."

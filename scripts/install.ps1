param(
    [switch]$Build,
    [int]$Port = 8015
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop ist nicht installiert oder nicht im PATH."
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop läuft nicht." }

$envFile = Join-Path $root ".env.docker"
if (-not (Test-Path -LiteralPath $envFile)) {
    $random = { [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant() }
    $content = Get-Content -LiteralPath (Join-Path $root ".env.docker.example") -Raw
    $content = $content.Replace("replace-with-a-long-random-password", (& $random))
    $content = $content.Replace("replace-with-at-least-32-random-bytes", (& $random))
    $content = $content.Replace("replace-with-a-long-random-api-key", (& $random))
    $content += "`nDASHBOARD_PORT=$Port`n"
    [IO.File]::WriteAllText($envFile, $content, [Text.UTF8Encoding]::new($false))
    Write-Host ".env.docker mit neuen, zufälligen Geheimnissen erstellt."
}

$arguments = @("compose", "--env-file", ".env.docker", "up", "-d")
if ($Build) { $arguments += "--build" }
& docker @arguments
if ($LASTEXITCODE -ne 0) { throw "Container konnten nicht gestartet werden." }

$deadline = (Get-Date).AddMinutes(3)
do {
    Start-Sleep -Seconds 3
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
        if ($health.status -eq "ok") {
            Write-Host "EventMonitorAI $($health.version) ist unter http://127.0.0.1:$Port erreichbar."
            exit 0
        }
    } catch { }
} while ((Get-Date) -lt $deadline)

docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs --tail 100 app
throw "Health-Check ist nach drei Minuten nicht erfolgreich."

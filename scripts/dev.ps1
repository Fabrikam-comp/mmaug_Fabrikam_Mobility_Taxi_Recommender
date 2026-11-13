<#
Local test setup. One command starts the real API on your computer and points
your local copy of the frontend at it, so you test in the browser like a user.

Start:                    powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
Undo the frontend edit:   powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Restore

Then open the site with VS Code Live Server at http://localhost:5500
(never 127.0.0.1, the saved login address uses localhost).
#>
param([switch]$Restore)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$configFile = "frontend/javascript/auth-config.js"

if ($Restore) {
    git update-index --no-skip-worktree $configFile
    git checkout -- $configFile
    Write-Host "auth-config.js is back to the committed version."
    exit 0
}

function Get-Setting($name) { [Environment]::GetEnvironmentVariable($name, "Process") }
function Set-Setting($name, $value) { [Environment]::SetEnvironmentVariable($name, $value, "Process") }
function Set-Default($name, $value) { if (-not (Get-Setting $name)) { Set-Setting $name $value } }

# 1. Load .env (lines like NAME=value; blank lines and # comments are skipped).
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host ".env not found. Copy .env.example to .env and fill it in." -ForegroundColor Red
    exit 1
}
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $at = $line.IndexOf("=")
    if ($at -lt 1) { return }
    $name = $line.Substring(0, $at).Trim()
    $value = $line.Substring($at + 1).Trim().Trim('"').Trim("'")
    Set-Setting $name $value
}

# 2. Local defaults. The mocks run inside the API, so the base URLs point at itself.
$mocksUrl = "http://127.0.0.1:8000/mocks"
Set-Default "CORS_ORIGIN" "http://localhost:5500"
Set-Default "BOLT_BASE_URL" $mocksUrl
Set-Default "UBER_BASE_URL" $mocksUrl
Set-Default "ECABS_BASE_URL" $mocksUrl
# The mock side must hold the same values as the API side.
Set-Default "MOCK_BOLT_CLIENT_ID" (Get-Setting "BOLT_CLIENT_ID")
Set-Default "MOCK_BOLT_CLIENT_SECRET" (Get-Setting "BOLT_CLIENT_SECRET")
Set-Default "MOCK_UBER_TOKEN" (Get-Setting "UBER_SERVER_TOKEN")
Set-Default "MOCK_ECABS_API_KEY" (Get-Setting "ECABS_API_KEY")

# 3. Stop early if the API cannot start without something. Only names are printed.
$required = "USER_ID_HMAC_KEY", "AZURE_AD_TENANTID", "AZURE_AD_CLIENTID",
            "COSMOS_ENDPOINT", "COSMOS_DATABASE", "COSMOS_CONTAINER_TRIPS"
$missing = $required | Where-Object { -not (Get-Setting $_) }
if ($missing) {
    Write-Host "Missing in .env:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  $_" }
    exit 1
}
$optional = "COSMOS_KEY", "GEOCODER_CONTACT", "GEOAPIFY_API_KEY",
            "BOLT_CLIENT_ID", "BOLT_CLIENT_SECRET", "UBER_SERVER_TOKEN", "ECABS_API_KEY"
foreach ($name in $optional) {
    if (-not (Get-Setting $name)) {
        Write-Host "Warning: $name is empty in .env" -ForegroundColor Yellow
    }
}

# 4. Put the local values into YOUR COPY of auth-config.js.
#    Same placeholders the Deploy workflow swaps. git is told to ignore this edit,
#    so it cannot be committed by accident. Undo with -Restore.
$full = Join-Path $root $configFile
$text = [System.IO.File]::ReadAllText($full)
$values = [ordered]@{
    "PASTE_CLIENT_ID_HERE"       = (Get-Setting "AZURE_AD_CLIENTID")
    "PASTE_TENANT_ID_HERE"       = (Get-Setting "AZURE_AD_TENANTID")
    "PASTE_BACKEND_API_URL_HERE" = "http://127.0.0.1:8000"
    "PASTE_GEOAPIFY_KEY_HERE"    = (Get-Setting "GEOAPIFY_API_KEY")
}
$changed = $false
foreach ($placeholder in $values.Keys) {
    $value = $values[$placeholder]
    if ($value -and $text.Contains($placeholder)) {
        $text = $text.Replace($placeholder, $value)
        $changed = $true
    }
}
if ($changed) {
    [System.IO.File]::WriteAllText($full, $text, (New-Object System.Text.UTF8Encoding($false)))
    git update-index --skip-worktree $configFile
    Write-Host "Local values written into $configFile (git ignores this edit)."
}
$left = [regex]::Matches($text, "PASTE_[A-Z_]+_HERE") | ForEach-Object { $_.Value } | Sort-Object -Unique
if ($left) {
    Write-Host "Still to fill in by hand in $configFile : $($left -join ', ')" -ForegroundColor Yellow
}

# 5. Start the real API.
Write-Host ""
Write-Host "API:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Site: open frontend/index.html with Live Server at http://localhost:5500" -ForegroundColor Green
Write-Host "Stop the API with Ctrl+C."
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000

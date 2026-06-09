# Build CyxcBot Windows distribution (onedir + Playwright Chromium).
param(
    [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================="
Write-Host "CyxcBot Windows Build"
Write-Host "Version: $Version"
Write-Host "=========================================="

# Build web frontend
Write-Host "Building web frontend..."
Push-Location web
if (Test-Path package-lock.json) {
    npm ci
} else {
    npm install
}
npm run build
if ($LASTEXITCODE -ne 0) { throw "Web frontend build failed" }
Pop-Location

# Python dependencies
Write-Host "Installing Python dependencies..."
pip install -r requirements.txt
pip install "pyinstaller>=6.0" tzdata

# Playwright browser (bundled into dist after PyInstaller)
Write-Host "Installing Playwright Chromium..."
playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Playwright install failed" }

# Build metadata (read by admin about page / startup logs)
$env:BUILD_VERSION = $Version
if (-not $env:GIT_COMMIT) {
    $env:GIT_COMMIT = (git rev-parse HEAD 2>$null)
    if (-not $env:GIT_COMMIT) { $env:GIT_COMMIT = "unknown" }
}
if (-not $env:BUILD_TIME) {
    $env:BUILD_TIME = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

# PyInstaller
Write-Host "Running PyInstaller..."
pyinstaller --noconfirm cyxcbot.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$distDir = Join-Path "dist" "cyxcbot"

# Bundle Playwright browsers next to the executable
$playwrightSrc = Join-Path $env:LOCALAPPDATA "ms-playwright"
$playwrightDst = Join-Path $distDir "ms-playwright"
if (Test-Path $playwrightSrc) {
    Write-Host "Copying Playwright browsers..."
    if (Test-Path $playwrightDst) { Remove-Item -Recurse -Force $playwrightDst }
    Copy-Item -Recurse -Force $playwrightSrc $playwrightDst
} else {
    Write-Warning "Playwright browsers not found at $playwrightSrc"
}

# Include example env for first-time setup
Copy-Item -Force env.example (Join-Path $distDir "env.example")

# Write build metadata (loaded at runtime via pyi_rth_build_info)
$buildInfo = @(
    "BUILD_VERSION=$Version",
    "GIT_COMMIT=$($env:GIT_COMMIT)",
    "GIT_TAG=$($env:GIT_TAG)",
    "GIT_BRANCH=$($env:GIT_BRANCH)",
    "BUILD_TIME=$($env:BUILD_TIME)",
    "BUILD_NUMBER=$($env:BUILD_NUMBER)"
) -join "`n"
$buildInfo | Out-File -FilePath (Join-Path $distDir "build-info.env") -Encoding utf8NoBOM

# Create zip archive
$zipName = "cyxcbot-windows-$Version.zip"
if (Test-Path $zipName) { Remove-Item -Force $zipName }
Write-Host "Creating archive: $zipName"
Compress-Archive -Path $distDir -DestinationPath $zipName

Write-Host "=========================================="
Write-Host "Build complete: $zipName"
Write-Host "Run: dist\cyxcbot\cyxcbot.exe"
Write-Host "=========================================="

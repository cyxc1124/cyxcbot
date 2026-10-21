$ErrorActionPreference = "Stop"
$buildScript = Join-Path $PSScriptRoot "../scripts/build-windows.ps1"
$workspace = Join-Path ([System.IO.Path]::GetTempPath()) ("cyxcbot-build-test-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path (Join-Path $workspace "web") -Force | Out-Null
$savedLocalAppData = $env:LOCALAPPDATA
$savedGitCommit = $env:GIT_COMMIT
$env:LOCALAPPDATA = Join-Path $workspace "AppData"
$env:GIT_COMMIT = "test-commit"
New-Item -ItemType Directory -Path (Join-Path $env:LOCALAPPDATA "ms-playwright") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $workspace "dist/cyxcbot") -Force | Out-Null
'{"packages":{"":{},"node_modules/react":{"version":"19.3.1"},"node_modules/tailwindcss":{"version":"4.3.3"}}}' |
    Set-Content (Join-Path $workspace "web/package-lock.json")

try {
    foreach ($failure in @("requirements", "tools", "tls", "playwright", "browser", "pyinstaller", "artifact")) {
        $global:CyxcBuildTestCalls = [System.Collections.Generic.List[string]]::new()
        $global:CyxcBuildTestFailure = $failure
        function npm { $global:LASTEXITCODE = 0 }
        function python {
            $command = $args -join " "
            $global:CyxcBuildTestCalls.Add($command)
            $global:LASTEXITCODE = 0
            if (($global:CyxcBuildTestFailure -eq "requirements" -and $command -eq "scripts/secure_pip.py install -r requirements.txt") -or
                ($global:CyxcBuildTestFailure -eq "tools" -and $command -eq "scripts/secure_pip.py install pyinstaller>=6.0 tzdata") -or
                ($global:CyxcBuildTestFailure -eq "tls" -and $command -like "-m pytest -q tests/test_aiohttp_tls.py*") -or
                ($global:CyxcBuildTestFailure -eq "playwright" -and $command -eq "scripts/playwright_install.py install chromium") -or
                ($global:CyxcBuildTestFailure -eq "browser" -and $command -like "-m pytest -q tests/test_browser_security.py*") -or
                ($global:CyxcBuildTestFailure -eq "pyinstaller" -and $command -eq "-m PyInstaller --noconfirm cyxcbot.spec") -or
                ($global:CyxcBuildTestFailure -eq "artifact" -and $command -like "scripts/check_tls_artifacts.py*")) {
                $global:LASTEXITCODE = 1
            }
        }

        Push-Location $workspace
        try {
            $expectedError = switch ($failure) {
                "requirements" { "Python dependency installation failed" }
                "tools" { "Packaging tool installation failed" }
                "tls" { "TLS trust regression checks failed" }
                "playwright" { "Playwright install failed" }
                "browser" { "Browser TLS regression checks failed" }
                "pyinstaller" { "PyInstaller build failed" }
                "artifact" { "Packaged CA bundle verification failed" }
            }
            try {
                & $buildScript -Version "test"
                throw "Build continued after a failed prerequisite check"
            } catch {
                if ($_.Exception.Message -ne $expectedError) { throw }
            }
            $expectedCalls = switch ($failure) {
                "requirements" { 1 }
                "tools" { 2 }
                "tls" { 3 }
                "playwright" { 4 }
                "browser" { 5 }
                "pyinstaller" { 6 }
                "artifact" { 7 }
            }
            if ($global:CyxcBuildTestCalls.Count -ne $expectedCalls) {
                throw "Playwright or PyInstaller ran after a failed prerequisite check"
            }
            if ($env:REACT_VERSION -ne "19.3.1" -or $env:TAILWIND_VERSION -ne "4.3.3") {
                throw "Failed to read versions from the lockfile containing an empty root key"
            }
        } finally {
            Pop-Location
        }
    }
} finally {
    $env:LOCALAPPDATA = $savedLocalAppData
    $env:GIT_COMMIT = $savedGitCommit
    Remove-Item -Recurse -Force $workspace
    Remove-Item Function:npm, Function:python
    Remove-Variable CyxcBuildTestCalls, CyxcBuildTestFailure -Scope Global
}
$global:LASTEXITCODE = 0
Write-Host "Windows build failure-path checks passed"

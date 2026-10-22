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
$global:CyxcBuildTestBrowserRoot = Join-Path $workspace "自定义 Playwright browsers"
New-Item -ItemType Directory -Path $global:CyxcBuildTestBrowserRoot -Force | Out-Null
'custom-browser' | Set-Content (Join-Path $global:CyxcBuildTestBrowserRoot "browser-marker.txt")
'# isolated test configuration' | Set-Content (Join-Path $workspace "env.example")
'{"packages":{"":{},"node_modules/react":{"version":"19.3.1"},"node_modules/tailwindcss":{"version":"4.3.3"}}}' |
    Set-Content (Join-Path $workspace "web/package-lock.json")

try {
    foreach ($failure in @("web_install", "web_build", "requirements", "tools", "tls", "playwright", "browser", "pyinstaller", "browser_path", "artifact", "none")) {
        $global:CyxcBuildTestCalls = [System.Collections.Generic.List[string]]::new()
        $global:CyxcBuildTestFailure = $failure
        function node {
            $global:LASTEXITCODE = 0
            $command = $args -join " "
            if (($global:CyxcBuildTestFailure -eq "web_install" -and $command -eq "../scripts/secure_npm.cjs ci") -or
                ($global:CyxcBuildTestFailure -eq "web_build" -and $command -eq "../scripts/secure_npm.cjs run build")) {
                $global:LASTEXITCODE = 1
            }
        }
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
                ($global:CyxcBuildTestFailure -eq "browser_path" -and $command -like "-X utf8 -c *") -or
                ($global:CyxcBuildTestFailure -eq "artifact" -and $command -like "scripts/check_tls_artifacts.py*")) {
                $global:LASTEXITCODE = 1
            }
            if ($command -like "-X utf8 -c *") { Write-Output $global:CyxcBuildTestBrowserRoot }
        }

        Push-Location $workspace
        try {
            $expectedError = switch ($failure) {
                "web_install" { "Web frontend build failed" }
                "web_build" { "Web frontend build failed" }
                "requirements" { "Python dependency installation failed" }
                "tools" { "Packaging tool installation failed" }
                "tls" { "TLS trust regression checks failed" }
                "playwright" { "Playwright install failed" }
                "browser" { "Browser TLS regression checks failed" }
                "pyinstaller" { "PyInstaller build failed" }
                "browser_path" { "Playwright browser location lookup failed" }
                "artifact" { "Packaged CA bundle verification failed" }
            }
            if ($failure -eq "none") {
                & $buildScript -Version "test"
                if ((Get-Content "dist/cyxcbot/ms-playwright/browser-marker.txt") -ne "custom-browser") {
                    throw "Build packaged a stale default browser instead of the resolved custom location"
                }
                if (-not (Test-Path "cyxcbot-windows-test.zip")) { throw "Build did not create the isolated test archive" }
            } else {
                try {
                    & $buildScript -Version "test"
                    throw "Build continued after a failed prerequisite check"
                } catch {
                    if ($_.Exception.Message -ne $expectedError) { throw }
                }
            }
            $expectedCalls = switch ($failure) {
                "web_install" { 0 }
                "web_build" { 0 }
                "requirements" { 1 }
                "tools" { 2 }
                "tls" { 3 }
                "playwright" { 4 }
                "browser" { 5 }
                "pyinstaller" { 6 }
                "browser_path" { 7 }
                "artifact" { 8 }
                "none" { 8 }
            }
            if ($global:CyxcBuildTestCalls.Count -ne $expectedCalls) {
                throw "Playwright or PyInstaller ran after a failed prerequisite check"
            }
            if ($failure -ne "web_install" -and ($env:REACT_VERSION -ne "19.3.1" -or $env:TAILWIND_VERSION -ne "4.3.3")) {
                throw "Failed to read versions from the lockfile containing an empty root key"
            }
        } finally {
            if ((Get-Location).Path -ne $workspace) { throw "Frontend failure changed the working directory" }
            Pop-Location
        }
    }
} finally {
    $env:LOCALAPPDATA = $savedLocalAppData
    $env:GIT_COMMIT = $savedGitCommit
    Remove-Item -Recurse -Force $workspace
    Remove-Item Function:node, Function:python
    Remove-Variable CyxcBuildTestCalls, CyxcBuildTestFailure, CyxcBuildTestBrowserRoot -Scope Global
}
$global:LASTEXITCODE = 0
Write-Host "Windows build failure-path and custom-browser checks passed"

$ErrorActionPreference = "Stop"
$buildScript = Join-Path $PSScriptRoot "../scripts/build-windows.ps1"
$workspace = Join-Path ([System.IO.Path]::GetTempPath()) ("cyxcbot-build-test-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path (Join-Path $workspace "web") -Force | Out-Null
'{"packages":{"":{},"node_modules/react":{"version":"19.3.1"},"node_modules/tailwindcss":{"version":"4.3.3"}}}' |
    Set-Content (Join-Path $workspace "web/package-lock.json")

try {
    foreach ($failure in @("requirements", "tools")) {
        $global:CyxcBuildTestCalls = [System.Collections.Generic.List[string]]::new()
        $global:CyxcBuildTestFailure = $failure
        function npm { $global:LASTEXITCODE = 0 }
        function python {
            $command = $args -join " "
            $global:CyxcBuildTestCalls.Add($command)
            $global:LASTEXITCODE = 0
            if (($global:CyxcBuildTestFailure -eq "requirements" -and $command -eq "-m pip install -r requirements.txt") -or
                ($global:CyxcBuildTestFailure -eq "tools" -and $command -eq "-m pip install pyinstaller>=6.0 tzdata")) {
                $global:LASTEXITCODE = 1
            }
        }

        Push-Location $workspace
        try {
            $expectedError = if ($failure -eq "requirements") { "Python dependency installation failed" } else { "Packaging tool installation failed" }
            try {
                & $buildScript -Version "test"
                throw "Build continued after a failed dependency install"
            } catch {
                if ($_.Exception.Message -ne $expectedError) { throw }
            }
            $expectedCalls = if ($failure -eq "requirements") { 1 } else { 2 }
            if ($global:CyxcBuildTestCalls.Count -ne $expectedCalls) {
                throw "Playwright or PyInstaller ran after a failed dependency install"
            }
            if ($env:REACT_VERSION -ne "19.3.1" -or $env:TAILWIND_VERSION -ne "4.3.3") {
                throw "Failed to read versions from the lockfile containing an empty root key"
            }
        } finally {
            Pop-Location
        }
    }
} finally {
    Remove-Item -Recurse -Force $workspace
    Remove-Item Function:npm, Function:python
    Remove-Variable CyxcBuildTestCalls, CyxcBuildTestFailure -Scope Global
}
$global:LASTEXITCODE = 0
Write-Host "Windows build failure-path checks passed"

# SpecForge installer for Windows.
#
# Usage:
#   .\scripts\install.ps1
#   powershell -ExecutionPolicy ByPass -NoProfile -File .\scripts\install.ps1
#   powershell -ExecutionPolicy ByPass -NoProfile -Command "iex (irm https://raw.githubusercontent.com/HsinPu/SpecForge/main/scripts/install.ps1)"

param(
    [string]$Repo = "https://github.com/HsinPu/SpecForge.git",
    [string]$Branch = "main",
    [string]$InstallDir = "$env:LOCALAPPDATA\SpecForge\SpecForge",
    [string]$ShimDir = "$env:LOCALAPPDATA\SpecForge\bin",
    [switch]$NoShim,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
} catch {
}

function Write-Info {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "OK  $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "!   $Message" -ForegroundColor Yellow
}

function Show-Help {
    Write-Host @"
SpecForge installer

Usage:
  .\scripts\install.ps1 [options]

Options:
  -Repo URL          Git repository URL for streamed installs.
  -Branch NAME      Git branch to install. Default: main.
  -InstallDir PATH  Install checkout path for streamed installs.
                    Default: %LOCALAPPDATA%\SpecForge\SpecForge
  -ShimDir PATH     Directory for the specforge command shim.
                    Default: %LOCALAPPDATA%\SpecForge\bin
  -NoShim           Do not create the specforge command shim.
  -Help             Show this help.

Local checkout behavior:
  Running this script from a cloned SpecForge repository installs that checkout
  into .venv and creates a specforge command shim.

Streamed behavior:
  Running through iex/irm clones or updates the repository at -InstallDir first.
"@
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory = (Get-Location).Path
    )

    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList 2>&1 | ForEach-Object { Write-Host $_ }
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    if ($exitCode -ne 0) {
        throw "Command failed with exit code ${exitCode}: $FilePath $($ArgumentList -join ' ')"
    }
}

function Resolve-LocalRepository {
    if (-not $PSScriptRoot) { return $null }

    $candidate = Split-Path $PSScriptRoot -Parent
    if ((Test-Path (Join-Path $candidate "pyproject.toml")) -and
        (Test-Path (Join-Path $candidate "src\specforge"))) {
        return [System.IO.Path]::GetFullPath($candidate)
    }

    return $null
}

function Resolve-Python {
    Write-Info "Checking Python 3.11+"

    $candidates = @(
        @{ Name = "py"; PrefixArgs = @("-3") },
        @{ Name = "python"; PrefixArgs = @() }
    )

    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue
        if (-not $command) { continue }

        $args = $candidate.PrefixArgs + @(
            "-c",
            "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
        )
        & $command.Source @args 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "$($candidate.Name) provides Python 3.11+"
            return @{ FilePath = $command.Source; PrefixArgs = $candidate.PrefixArgs }
        }
    }

    throw "Python 3.11+ was not found. Install it from https://www.python.org/downloads/ and re-run this installer."
}

function Ensure-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) { return }
    throw "Git was not found. Install Git for Windows from https://git-scm.com/download/win and re-run this installer."
}

function Install-Repository {
    Write-Info "Installing repository to $InstallDir"
    Ensure-Git

    $parent = Split-Path $InstallDir -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null

    if (Test-Path (Join-Path $InstallDir ".git")) {
        Push-Location $InstallDir
        try {
            Invoke-Checked git @("-c", "windows.appendAtomically=false", "fetch", "origin")
            Invoke-Checked git @("-c", "windows.appendAtomically=false", "checkout", $Branch)
            Invoke-Checked git @("-c", "windows.appendAtomically=false", "pull", "--ff-only", "origin", $Branch)
        } finally {
            Pop-Location
        }
        return
    }

    if (Test-Path $InstallDir) {
        throw "Install path exists but is not a git checkout: $InstallDir"
    }

    Invoke-Checked git @(
        "-c", "windows.appendAtomically=false",
        "clone",
        "--branch", $Branch,
        $Repo,
        $InstallDir
    )
}

function Install-Package {
    param(
        [hashtable]$Python,
        [string]$SourceDir
    )

    $venvDir = Join-Path $SourceDir ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"

    if (-not (Test-Path $venvPython)) {
        Write-Info "Creating virtual environment"
        Invoke-Checked $Python.FilePath ($Python.PrefixArgs + @("-m", "venv", $venvDir))
    }

    Write-Info "Installing SpecForge package"
    Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip") $SourceDir
    Invoke-Checked $venvPython @("-m", "pip", "install", "-e", ".") $SourceDir

    return $venvPython
}

function Add-UserPathEntry {
    param([string]$PathEntry)

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $items = if ($userPath) { $userPath -split ";" } else { @() }
    if ($items -notcontains $PathEntry) {
        $items += $PathEntry
        [Environment]::SetEnvironmentVariable("Path", ($items -join ";"), "User")
        Write-Success "Added $PathEntry to user PATH"
    }

    if (($env:Path -split ";") -notcontains $PathEntry) {
        $env:Path = "$PathEntry;$env:Path"
    }
}

function Install-Shim {
    param(
        [string]$VenvPython,
        [string]$SourceDir
    )

    if ($NoShim) { return }

    New-Item -ItemType Directory -Force -Path $ShimDir | Out-Null

    $shimPath = Join-Path $ShimDir "specforge.cmd"
    $shimContent = @"
@echo off
REM Generated by SpecForge installer.
"$VenvPython" -m specforge %*
"@
    Set-Content -Encoding ASCII -Path $shimPath -Value $shimContent
    Write-Success "Created command shim: $shimPath"

    $metaPath = Join-Path $ShimDir "specforge-install.txt"
    Set-Content -Encoding UTF8 -Path $metaPath -Value "SourceDir=$SourceDir`nPython=$VenvPython"

    Add-UserPathEntry $ShimDir
}

if ($Help) {
    Show-Help
    exit 0
}

$localRepository = Resolve-LocalRepository
$sourceDir = $null

if ($localRepository -and -not $PSBoundParameters.ContainsKey("InstallDir")) {
    $InstallDir = $localRepository
    $sourceDir = $localRepository
    Write-Info "Using local checkout: $sourceDir"
} else {
    Install-Repository
    $sourceDir = [System.IO.Path]::GetFullPath($InstallDir)
}

$python = Resolve-Python
$venvPython = Install-Package -Python $python -SourceDir $sourceDir
Install-Shim -VenvPython $venvPython -SourceDir $sourceDir

Write-Info "Verifying SpecForge"
Invoke-Checked $venvPython @("-m", "specforge", "--version") $sourceDir

Write-Success "SpecForge installation complete"
Write-Host ""
Write-Host "Usage:"
Write-Host "  cd C:\path\to\project"
Write-Host "  specforge init"
Write-Host ""
Write-Host "Update later:"
Write-Host "  specforge update"
Write-Host ""
Write-Host "If this is a new terminal and specforge is not found, reopen the terminal once."

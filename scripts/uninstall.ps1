# SpecForge uninstaller for Windows installs created by scripts/install.ps1.

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\SpecForge\SpecForge",
    [string]$ShimDir = "$env:LOCALAPPDATA\SpecForge\bin",
    [switch]$RemoveCode,
    [switch]$Yes,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

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
SpecForge uninstaller

Usage:
  .\scripts\uninstall.ps1 [options]

Options:
  -InstallDir PATH  Installed checkout path.
  -ShimDir PATH     Directory containing the specforge command shim.
  -RemoveCode       Remove the installed checkout directory after removing .venv.
                    Local checkout code is kept unless this flag is present.
  -Yes              Do not prompt for confirmation.
  -Help             Show this help.
"@
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

function Test-UnsafePath {
    param([string]$Path)
    if (-not $Path) { return $true }

    $resolved = [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
    $root = [System.IO.Path]::GetPathRoot($resolved).TrimEnd("\")
    $home = [System.IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd("\")
    return ($resolved -eq $root -or $resolved -eq $home)
}

function Confirm-Uninstall {
    if ($Yes) { return }

    Write-Host "SpecForge uninstall will remove:"
    Write-Host "  Virtual environment: $(Join-Path $InstallDir ".venv")"
    Write-Host "  Command shim:        $(Join-Path $ShimDir "specforge.cmd")"
    if ($RemoveCode) {
        Write-Host "  Code directory:      $InstallDir"
        Write-Warn "RemoveCode deletes the installed checkout directory."
    } else {
        Write-Host "  Code directory:      kept at $InstallDir"
    }
    Write-Host ""
    $answer = Read-Host "Type 'yes' to continue"
    if ($answer -ne "yes") {
        Write-Host "Uninstall cancelled."
        exit 0
    }
}

function Remove-Shim {
    $shimPath = Join-Path $ShimDir "specforge.cmd"
    if (-not (Test-Path $shimPath)) {
        Write-Info "Command shim not found: $shimPath"
        return
    }

    $content = Get-Content -Raw -Path $shimPath -ErrorAction SilentlyContinue
    if ($content -and $content.Contains($InstallDir)) {
        Remove-Item -Force $shimPath
        Write-Success "Removed $shimPath"
    } else {
        Write-Warn "Not removing $shimPath because it was not created for $InstallDir"
    }
}

function Remove-Venv {
    $venvDir = Join-Path $InstallDir ".venv"
    if (Test-Path $venvDir) {
        Remove-Item -Recurse -Force -LiteralPath $venvDir
        Write-Success "Removed $venvDir"
    } else {
        Write-Info "Virtual environment not found: $venvDir"
    }
}

function Remove-Code {
    if (-not $RemoveCode) { return }

    if (Test-UnsafePath $InstallDir) {
        throw "Refusing to remove unsafe install path: $InstallDir"
    }

    if (Test-Path $InstallDir) {
        Remove-Item -Recurse -Force -LiteralPath $InstallDir
        Write-Success "Removed $InstallDir"
    } else {
        Write-Info "Code directory not found: $InstallDir"
    }
}

if ($Help) {
    Show-Help
    exit 0
}

$localRepository = Resolve-LocalRepository
if ($localRepository -and -not $PSBoundParameters.ContainsKey("InstallDir")) {
    $InstallDir = $localRepository
}

Confirm-Uninstall
Remove-Shim
Remove-Venv
Remove-Code

Write-Success "SpecForge uninstall complete"

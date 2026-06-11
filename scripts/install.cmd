@echo off
REM SpecForge installer for Windows CMD users.

set "SCRIPT_DIR=%~dp0"

echo.
echo  SpecForge Installer
echo  Launching PowerShell installer...
echo.

powershell -ExecutionPolicy ByPass -NoProfile -File "%SCRIPT_DIR%install.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Installation failed. Try running PowerShell directly:
    echo    powershell -ExecutionPolicy ByPass -NoProfile -File "%SCRIPT_DIR%install.ps1"
    echo.
    pause
    exit /b 1
)

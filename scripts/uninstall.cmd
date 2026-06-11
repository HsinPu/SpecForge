@echo off
REM SpecForge uninstaller for Windows CMD users.

set "SCRIPT_DIR=%~dp0"

echo.
echo  SpecForge Uninstaller
echo  Launching PowerShell uninstaller...
echo.

powershell -ExecutionPolicy ByPass -NoProfile -File "%SCRIPT_DIR%uninstall.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Uninstall failed. Try running PowerShell directly:
    echo    powershell -ExecutionPolicy ByPass -NoProfile -File "%SCRIPT_DIR%uninstall.ps1"
    echo.
    pause
    exit /b 1
)

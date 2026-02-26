::This script copies my Sync_Main directory to my USB

@echo off
setlocal
set "SOURCE=C:\Users\white\OneDrive\Documents\Sync_Main"
set "LABEL=CDB-USB"

:: Find USB drive letter by label using PowerShell
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "(Get-Volume | Where-Object { $_.FileSystemLabel -eq '%LABEL%' } | Select-Object -ExpandProperty DriveLetter)"') do set "DRIVE=%%i"

if not defined DRIVE (
    echo USB '%LABEL%' not found. Exiting...
    exit /b
)

set "DEST=%DRIVE%:\Sync_USB"

robocopy "%SOURCE%" "%DEST%" /MIR /R:2 /W:5 /FFT >nul

exit /b

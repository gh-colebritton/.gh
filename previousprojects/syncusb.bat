::This script copies my sync_main directory to my sync_usb 

@echo off
setlocal
set "SOURCE=C:\Users\white\OneDrive\Documents\sync_main"
set "LABEL=CDB-USB"

:: Find USB drive letter by label using PowerShell
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "(Get-Volume | Where-Object { $_.FileSystemLabel -eq '%LABEL%' } | Select-Object -ExpandProperty DriveLetter)"') do set "DRIVE=%%i"

if not defined DRIVE (
    echo USB '%LABEL%' not found. Exiting...
    exit /b
)

set "DEST=%DRIVE%:\sync_usb"

robocopy "%SOURCE%" "%DEST%" /MIR /R:2 /W:5 /FFT >nul

exit /b

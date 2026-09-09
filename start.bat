@echo off
setlocal enabledelayedexpansion

echo ==============================================================================
echo                SideDoor AI - Autonomous Career Networking Engine
echo ==============================================================================
echo.

:: Detect Python interpreter
set "PY_CMD="

if exist "C:\ProgramData\anaconda3\python.exe" (
    set "PY_CMD=C:\ProgramData\anaconda3\python.exe"
    goto :FoundPython
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py -3"
    goto :FoundPython
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :FoundPython
)

echo [ERROR] Python was not detected on your system.
echo Please install Python 3.10+ or Anaconda from https://www.python.org/
pause
exit /b 1

:FoundPython
echo [SideDoor] Using Python interpreter: !PY_CMD!

:: Initialize .env if missing
if not exist ".env" (
    if exist ".env.example" (
        echo [SideDoor] Initializing .env from template...
        copy .env.example .env >nul
    )
)

:: Reset port marker
if exist ".active_port" del ".active_port"

:: Start web server
echo [SideDoor] Starting SideDoor AI local dashboard...
echo.

:: Open browser in background once port is determined
start "" cmd /c "timeout /t 2 /nobreak >nul & for /f \"usebackq delims=\" %%p in (`type .active_port 2^>nul ^|^| echo 8080`) do (start http://localhost:%%p)"

:: Run application
!PY_CMD! app.py

pause

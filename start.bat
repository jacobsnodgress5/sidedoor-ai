@echo off
setlocal enabledelayedexpansion
title SideDoor AI - Quickstart Launcher

echo ==============================================================================
echo                SideDoor AI - Autonomous Career Networking Engine
echo ==============================================================================
echo.

:: 1. Detect Python interpreter
set "PY_CMD="

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :CheckPythonVersion
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py -3"
    goto :CheckPythonVersion
)

if exist "C:\ProgramData\anaconda3\python.exe" (
    set "PY_CMD=C:\ProgramData\anaconda3\python.exe"
    goto :CheckPythonVersion
)

if exist "%USERPROFILE%\anaconda3\python.exe" (
    set "PY_CMD=%USERPROFILE%\anaconda3\python.exe"
    goto :CheckPythonVersion
)

echo [ERROR] Python 3.10+ was not detected on your system.
echo Please download and install Python from: https://www.python.org/downloads/
echo (Make sure to check "Add Python to PATH" during installation!)
echo.
pause
exit /b 1

:CheckPythonVersion
echo [1/5] Python detected: !PY_CMD!

:: 2. Check or create Virtual Environment (.venv)
if not exist ".venv\Scripts\python.exe" (
    echo [2/5] Creating isolated Python virtual environment (.venv)...
    !PY_CMD! -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo [Warning] Could not create .venv. Falling back to system Python.
        set "APP_PYTHON=!PY_CMD!"
    ) else (
        echo [SideDoor] Virtual environment created successfully.
        set "APP_PYTHON=.venv\Scripts\python.exe"
    )
) else (
    set "APP_PYTHON=.venv\Scripts\python.exe"
    echo [2/5] Using virtual environment: .venv
)

:: 3. Install dependencies & Playwright Chromium if first run
if not exist ".venv\.deps_installed" (
    echo [3/5] Installing dependencies (first run only, may take 1-2 minutes)...
    !APP_PYTHON! -m pip install --upgrade pip >nul 2>&1
    !APP_PYTHON! -m pip install -r requirements.txt
    echo [SideDoor] Installing Playwright browser for LinkedIn scraper...
    !APP_PYTHON! -m playwright install chromium
    echo done > ".venv\.deps_installed"
    echo [SideDoor] Dependencies installed successfully.
) else (
    echo [3/5] Dependencies are up to date.
)

:: 4. Check API Keys (.env)
if not exist ".env" (
    echo.
    echo ==============================================================================
    echo                           STEP: API KEY SETUP
    echo ==============================================================================
    echo SideDoor AI runs 100%% locally, but uses 2 free API keys for intelligence:
    echo   1. Gemini API Key (Free): https://aistudio.google.com/app/apikey
    echo   2. Hunter.io API Key (Free 25-50/mo): https://hunter.io/api
    echo.
    set /p "USER_GEMINI=Paste your Gemini API Key (or press ENTER to configure later in UI): "
    set /p "USER_HUNTER=Paste your Hunter.io API Key (or press ENTER to configure later in UI): "
    
    (
        echo GEMINI_API_KEY="!USER_GEMINI!"
        echo HUNTER_API_KEY="!USER_HUNTER!"
    ) > .env
    echo [SideDoor] Configuration saved to .env
    echo.
)

:: 5. Check LinkedIn Scraper Authentication (scraper/auth.json)
if not exist "scraper\auth.json" (
    echo.
    echo ==============================================================================
    echo                     STEP: ONE-TIME LINKEDIN LOGIN
    echo ==============================================================================
    echo To discover active job postings, SideDoor saves a secure session cookie
    echo locally into scraper\auth.json so LinkedIn allows the search scraper.
    echo.
    echo A browser window will now open. Please:
    echo   1. Log into your LinkedIn account.
    echo   2. Once your feed loads, come back to this window and press ENTER.
    echo.
    set /p "CONFIRM_LOGIN=Press ENTER to open LinkedIn login now (or type S to skip)... "
    if /i not "!CONFIRM_LOGIN!"=="S" (
        !APP_PYTHON! scraper\login.py
        if exist "scraper\auth.json" (
            echo [SideDoor] LinkedIn authentication saved successfully!
        ) else (
            echo [Notice] auth.json not detected. You can run 'python scraper/login.py' anytime.
        )
    )
    echo.
)

:: 6. Launch Application Server
echo [5/5] Launching SideDoor AI Web Dashboard...
echo.
echo ==============================================================================
echo  SideDoor AI is starting!
echo  Opening http://localhost:8080 in your browser...
echo  (Keep this terminal window open while using SideDoor AI)
echo ==============================================================================
echo.

:: Open browser automatically after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8080"

:: Start server
!APP_PYTHON! app.py

pause

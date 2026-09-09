@echo off
:: Change directory to where this batch file is located
cd /d "%~dp0"

echo Running LinkedIn Job Scraper Pipeline...
echo Date: %DATE% %TIME%

:: If you are using a virtual environment, activate it here
:: call venv\Scripts\activate

:: Execute the orchestrator script using explicit Python path
"C:\ProgramData\anaconda3\python.exe" main.py

echo Pipeline Execution Finished.

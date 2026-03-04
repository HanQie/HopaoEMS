@echo off
setlocal enabledelayedexpansion

TITLE HopaoEMS Bootstrapper

echo ========================================
echo        HopaoEMS STARTUP SEQUENCE
echo ========================================

:: 1. Environment Check
if not exist .venv (
    echo [ERROR] .venv folder not found.
    echo Please create a virtual environment first: python -m venv .venv
    pause
    exit /b 1
)

echo [1/3] Activating Virtual Environment...
call .venv\Scripts\activate

:: 2. Dependencies Check
echo [2/3] Syncing Dependencies (requirements.txt)...
pip install -r requirements.txt --quiet

:: 3. Port Occupancy Check & Auto-Jump
set /a "PORT=5000"
set "MAX_RETRIES=10"
set "COUNT=0"

:CHECK_PORT
netstat -ano | findstr "LISTENING" | findstr ":!PORT! " >nul
if !errorlevel! equ 0 (
    echo [WARN] Port !PORT! is currently occupied.
    set /a "PORT=!PORT! + 1"
    set /a "COUNT=!COUNT! + 1"
    if !COUNT! geq !MAX_RETRIES! (
        echo [ERROR] Could not find an empty port after !MAX_RETRIES! attempts.
        pause
        exit /b 1
    )
    goto :CHECK_PORT
)

echo [3/3] Dynamic Port Assigned: !PORT!
echo ----------------------------------------
echo Starting Application...
echo (Check http://localhost:!PORT! once ready)
echo ----------------------------------------

:: 4. Launch
python src/run.py !PORT!

if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL] Application exited with error code %errorlevel%.
    pause
)

exit /b 0

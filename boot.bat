@echo off
setlocal enabledelayedexpansion

TITLE HopaoEMS Bootstrapper

echo ========================================
echo        HopaoEMS STARTUP SEQUENCE
echo ========================================

:: 1. Environment & Integrity Check
if not exist .venv\Scripts\activate.bat (
    echo [WARN] .venv/Scripts/activate.bat not found. 
    echo [1/3] Creating virtual environment...
    if exist .venv rmdir /s /q .venv
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment. 
        echo Please ensure Python is installed and in your PATH.
        pause
        exit /b 1
    )
)

echo [1/3] Activating Virtual Environment...
call .venv\Scripts\activate

:: 2. Dependencies Check (Ensuring we use the VENV's python)
echo [2/3] Syncing Dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet

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

:: Find Local IP for easy LAN access
for /f "delims=[] tokens=2" %%a in ('ping -4 -n 1 %COMPUTERNAME% ^| findstr [') do set LOCAL_IP=%%a

echo ----------------------------------------
echo Starting Application...
echo Local Access: http://localhost:!PORT!
if defined LOCAL_IP (
    echo LAN Access:   http://!LOCAL_IP!:!PORT!
)
echo ----------------------------------------

:: 4. Launch
python src/run.py !PORT!

if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL] Application exited with error code %errorlevel%.
    pause
)

exit /b 0

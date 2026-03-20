@echo off
setlocal
title HopaoEMS Launcher (Ollama)

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Virtual environment not found.
    echo Expected: %PYTHON%
    pause
    exit /b 1
)

:MENU
cls
echo =======================================================
echo          HopaoEMS Launcher (Ollama)
echo =======================================================
echo.
echo   1. Start HopaoEMS (Normal)
echo   2. Start HopaoEMS (Skip GATE)
echo   0. Exit
echo.
echo =======================================================
set choice=
set /p choice="Select (0-2): "

if "%choice%"=="1" set "SKIP_GATES=false" & goto START_APP
if "%choice%"=="2" set "SKIP_GATES=true" & goto START_APP
if "%choice%"=="0" exit /b 0

echo Invalid choice. Try again.
timeout /t 2 >nul
goto MENU

:START_APP
echo.
echo [Info] Starting HopaoEMS with Ollama backend...
echo [Info] URL: http://localhost:8080
echo [Info] Press Ctrl+C to stop.
echo.

rem Start Flask on port 8080
"%PYTHON%" "%PROJECT_ROOT%\src\run.py" 8080

echo.
echo Server stopped.
pause
goto MENU

@echo off
if not exist .venv\Scripts\activate.bat goto novenv

goto proceed

:novenv
echo [ERROR] Virtual environment (.venv) not found. Run boot.bat first.
exit /b 1

:proceed
set PYTHONPATH=src
.venv\Scripts\python.exe src/hopaoems/contracts/run_gates.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [GATE] FAILED! Stop and check errors.
    exit /b 1
)
echo.
echo [GATE] ALL PASSED.
exit /b 0

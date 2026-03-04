@echo off
set PYTHONPATH=src
python src/hopaoems/contracts/run_gates.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [GATE] FAILED! Stop and check errors.
    exit /b 1
)
echo.
echo [GATE] ALL PASSED.
exit /b 0

@echo off
setlocal
cd /d "%~dp0"

set LOG_FILE=%~dp0error.log
echo [%date% %time%] Starting Multi Paste > "%LOG_FILE%"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -m venv .venv >> "%LOG_FILE%" 2>&1
    if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto failed

".venv\Scripts\python.exe" multi_paste_tool.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto failed

exit /b 0

:failed
echo.
echo Multi Paste failed to start.
echo.
echo Error log:
type "%LOG_FILE%"
echo.
pause
exit /b 1

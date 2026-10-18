@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_CMD="
set "VENV_PYTHON=.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" goto have_venv

where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if "%PYTHON_CMD%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if "%PYTHON_CMD%"=="" (
    where python3 >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python3"
)

if not "%PYTHON_CMD%"=="" (
    echo Using Python: %PYTHON_CMD%
    %PYTHON_CMD% -m venv .venv
) else (
    echo Python was not found by cmd. Trying PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "python -m venv .venv"
)

:have_venv

if not exist "%VENV_PYTHON%" (
    echo Failed to create virtual environment.
    echo Install Python 3.11+ and make sure it works in cmd or PowerShell.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto fail

"%VENV_PYTHON%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail

"%VENV_PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name CloudInitBuilder ^
    --collect-all customtkinter ^
    main.py
if errorlevel 1 goto fail

echo.
echo Build finished: dist\CloudInitBuilder.exe
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1

@echo off
setlocal enabledelayedexpansion
title Google Photos Local Takeout Archive

echo ==============================================================================
echo   GOOGLE PHOTOS LOCAL TAKEOUT ARCHIVE LAUNCHER
echo ==============================================================================

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: Prevent Windows OpenBLAS / OpenMP thread contention
set "OPENBLAS_NUM_THREADS=1"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"

:: 1. Check for dedicated local virtualenv in project root (.venv)
if exist "%PROJECT_DIR%.venv\Scripts\python.exe" (
    echo [+] Using local virtual environment: .venv
    set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"
    goto :RUN_SERVER
)

:: 2. Check for standard venv folder (venv)
if exist "%PROJECT_DIR%venv\Scripts\python.exe" (
    echo [+] Using local virtual environment: venv
    set "PYTHON_EXE=%PROJECT_DIR%venv\Scripts\python.exe"
    goto :RUN_SERVER
)

:: 3. Check for nearby complete venv in Google Photos folder if available
if exist "E:\Takeout\Google Photos\local-google-photos\.venv\Scripts\python.exe" (
    echo [+] Using existing AI-enabled virtual environment in Google Photos folder
    set "PYTHON_EXE=E:\Takeout\Google Photos\local-google-photos\.venv\Scripts\python.exe"
    goto :RUN_SERVER
)

:: 4. Fallback to system python
where python >nul 2>nul
if %errorlevel% equ 0 (
    echo [+] Using system Python...
    set "PYTHON_EXE=python"
    goto :RUN_SERVER
)

echo [!] ERROR: Python executable not found on system PATH.
echo     Please install Python 3.10+ or create a virtual environment in .venv.
pause
exit /b 1

:RUN_SERVER
echo [+] Launching application via run.py...
echo ==============================================================================
"%PYTHON_EXE%" run.py %*
if %errorlevel% neq 0 (
    echo.
    echo [!] Application exited with code %errorlevel%.
    pause
)

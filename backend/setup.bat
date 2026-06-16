@echo off
setlocal
title AI Job Scraper — Setup & Start
cd /d "%~dp0"

echo.
echo  ╔═══════════════════════════════════════╗
echo  ║     AI Job Scraper — Windows Setup    ║
echo  ╚═══════════════════════════════════════╝
echo.

:: Read PORT from .env if it exists, default to 3000
set TARGET_PORT=3000
if exist ".env" (
    for /f "usebackq tokens=1,2 delims==" %%i in (".env") do (
        if "%%i"=="PORT" set TARGET_PORT=%%j
    )
)

echo  Checking for existing processes on port %TARGET_PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%TARGET_PORT% ^| findstr LISTENING') do (
    echo  [PROCESS] Killing existing process PID %%a running on port %TARGET_PORT%...
    taskkill /f /pid %%a >nul 2>&1
)



:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Please install Python 3.8+ and ensure "Add Python to PATH" is checked.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do set PYTHON_VER=%%v
echo  [OK] Python %PYTHON_VER% found

:: Setup Python virtual environment
echo.
echo  [1/5] Setting up Python virtual environment...
if not exist "nlp_service\venv_nlp" (
    call python -m venv nlp_service\venv_nlp
)

echo  [2/5] Upgrading pip and installing requirements...
call .\nlp_service\venv_nlp\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
call .\nlp_service\venv_nlp\Scripts\pip.exe install -r .\nlp_service\requirements.txt
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)
echo  [OK] Python virtual environment ready

:: Create .env if not exists
echo.
echo  [3/5] Setting up environment file...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo  [OK] .env created from template
    echo.
    echo  ┌─────────────────────────────────────────────────┐
    echo  │  ACTION REQUIRED: Edit backend\.env              │
    echo  │                                                   │
    echo  │  Set your Gmail credentials:                      │
    echo  │    EMAIL_USER=your_email@gmail.com                │
    echo  │    EMAIL_PASS=your_16_char_app_password           │
    echo  │    NOTIFY_EMAIL=your_email@gmail.com              │
    echo  │                                                   │
    echo  │  Gmail App Password guide:                        │
    echo  │  myaccount.google.com → Security →               │
    echo  │  2-Step Verification → App passwords              │
    echo  └─────────────────────────────────────────────────┘
) else (
    echo  [OK] .env already exists — skipping
)

:: Create required directories
echo.
echo  [4/5] Creating directories...
if not exist "data"    mkdir data
echo  [OK] Directories ready


:: Import resume automatically from workspace root
echo.
echo  [5/5] Importing resume from root workspace...
call .\nlp_service\venv_nlp\Scripts\python.exe nlp_service\import_resume.py
if %errorlevel% neq 0 (
    echo  [WARNING] Resume import failed.
    echo  Please ensure the PDF resume is in the root directory
    echo  (e.g., C:\Users\saura\Desktop\Antigravity\Agent1)
) else (
    echo  [OK] Resume imported successfully!
)

:: Start the server
echo.
echo  Starting the FastAPI Server...
echo  Press Ctrl+C at any time to stop.
echo.
call .\nlp_service\venv_nlp\Scripts\python.exe -u nlp_service\app.py

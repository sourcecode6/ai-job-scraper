@echo off
setlocal
title AI Job Scraper — Setup & Start

echo.
echo  ╔═══════════════════════════════════════╗
echo  ║     AI Job Scraper — Windows Setup    ║
echo  ╚═══════════════════════════════════════╝
echo.

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Node.js is not installed or not in PATH.
    echo  Please install from: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set NODE_VER=%%v
echo  [OK] Node.js %NODE_VER% found

:: Navigate to the backend directory where this batch file is
cd /d "%~dp0"

:: Install npm dependencies
echo.
echo  [1/6] Installing dependencies...
call npm install
if %errorlevel% neq 0 (
    echo  [ERROR] npm install failed.
    pause
    exit /b 1
)
echo  [OK] Dependencies installed

:: Playwright installation skipped (Python scraper does not require Playwright)

:: Setup C++ native addon and Python FastAPI
echo.
echo  [2.5/6] Setting up Hybrid Python & C++ components...

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [WARNING] Python is not installed or not in PATH.
    echo  The NLP service will fallback to local Node.js transformers.
) else (
    echo  [OK] Python found
    echo  Setting up Python virtual environment...
    if not exist "nlp_service\venv_nlp" (
        call python -m venv nlp_service\venv_nlp
    )
    echo  Installing Python requirements...
    call .\nlp_service\venv_nlp\Scripts\pip.exe install -r .\nlp_service\requirements.txt
    echo  [OK] Python virtual environment ready
)

:: Attempt C++ native addon compilation
echo.
echo  Attempting to compile C++ native addon...
call npm run build-addon
if %errorlevel% neq 0 (
    echo  [WARNING] C++ compilation failed (Visual Studio Build Tools missing).
    echo  The similarity matching will fallback to pure JavaScript.
) else (
    echo  [OK] C++ native addon compiled successfully!
)

:: Create .env if not exists
echo.
echo  [3/6] Setting up environment file...
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
echo  [4/6] Creating directories...
if not exist "data"    mkdir data
if not exist "logs"    mkdir logs
if not exist "uploads" mkdir uploads
echo  [OK] Directories ready



:: Import resume automatically from workspace root
echo.
echo  [5/6] Importing resume from root workspace...
call node src/scripts/importResume.js
if %errorlevel% neq 0 (
    echo  [WARNING] Resume import failed.
    echo  Please ensure the PDF resume is in the root directory
    echo  (e.g., C:\Users\saura\Desktop\Antigravity\Agent1)
) else (
    echo  [OK] Resume imported successfully!
)

:: Start the server
echo.
echo  [6/6] Starting the server...
echo  Press Ctrl+C at any time to stop.
echo.
call npm start

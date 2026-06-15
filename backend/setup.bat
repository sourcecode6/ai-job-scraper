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

:: Install Playwright browsers (Chromium only)
echo.
echo  [2/6] Installing Playwright Chromium browser...
call npx playwright install chromium
echo  [OK] Playwright Chromium ready

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

:: Check if HF_API_KEY in .env is still the default placeholder
findstr /C:"HF_API_KEY=your_hf_token_here" .env >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo  ┌─────────────────────────────────────────────────┐
    echo  │  WARNING: HF_API_KEY is not set in backend\.env   │
    echo  │  The HuggingFace API key is required to avoid    │
    echo  │  rate-limiting and 401 unauthorized responses.   │
    echo  │  Please add a free Read token from:              │
    echo  │  https://huggingface.co/settings/tokens          │
    echo  └─────────────────────────────────────────────────┘
    echo.
)

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

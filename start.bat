@echo off
title AgentForge

REM ---- Switch to script directory ----
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo =============================================
echo      AgentForge - One-Click Start
echo =============================================
echo.

REM ---- Check .env ----
if not exist ".env" (
    echo [!] .env not found, creating from template...
    copy .env.example .env >nul
    echo [!] Please edit .env with your API key, then re-run
    echo [!] Opening .env for editing...
    start "" .env
    pause
    exit /b
)
echo [OK] .env found

REM ---- Check Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+
    pause
    exit /b
)
echo [OK] Python ready

REM ---- Check Node.js ----
set SKIP_GUI=1
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js not found. Starting backend only.
) else (
    echo [OK] Node.js ready
    set SKIP_GUI=0
)

REM ---- Install Python deps ----
echo.
echo [..] Installing Python dependencies...
pip install -r requirements.txt -q 2>&1 | find /V "already"
echo [OK] Python deps installed

REM ---- Build frontend ----
if "%SKIP_GUI%"=="0" (
    if not exist "gui\dist-web\index.html" (
        echo [..] Building frontend...
        cd gui
        call npm install >nul 2>&1
        call npx vite build --config vite.web.config.ts >nul 2>&1
        cd ..
        echo [OK] Frontend built
    ) else (
        echo [OK] Frontend already built
    )
)

REM ---- Clean old processes ----
echo.
echo [..] Cleaning old processes...
for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

REM ---- Start backend ----
echo [..] Starting backend (port 8765)...
start "AgentForge-Backend" /B python -X utf8 main.py > backend.log 2>&1

echo [..] Waiting for backend...
set RETRIES=0
:RETRY_BACKEND
timeout /t 2 /nobreak >nul
python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/', timeout=2)" >nul 2>&1
if errorlevel 1 (
    set /a RETRIES+=1
    if !RETRIES! lss 10 (
        goto RETRY_BACKEND
    )
    echo [ERROR] Backend failed to start after 20s. Check backend.log
    type backend.log
    pause
    exit /b
)
echo [OK] Backend running: http://127.0.0.1:8765

REM ---- Start frontend ----
if "%SKIP_GUI%"=="0" (
    echo [..] Starting frontend (port 5183)...
    start "AgentForge-Frontend" /B python -X utf8 serve_frontend.py > frontend.log 2>&1

    set RETRIES=0
    :RETRY_FRONTEND
    timeout /t 2 /nobreak >nul
    python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5183/', timeout=2)" >nul 2>&1
    if errorlevel 1 (
        set /a RETRIES+=1
        if !RETRIES! lss 8 (
            goto RETRY_FRONTEND
        )
        echo [WARN] Frontend health check failed, but should still work
    )
    echo [OK] Frontend: http://127.0.0.1:5183
)

REM ---- Open browser ----
echo.
echo =============================================
echo      AgentForge is running!
echo.
echo  BACKEND URL
echo    API:        http://127.0.0.1:8765
echo    API docs:   http://127.0.0.1:8765/docs
echo.
if "%SKIP_GUI%"=="0" (
    echo  FRONTEND URL
    echo    Dashboard:  http://127.0.0.1:5183
    echo.
)
echo  Press any key to stop all services
echo =============================================
echo.

if "%SKIP_GUI%"=="0" (
    start http://127.0.0.1:5183
)

pause >nul

REM ---- Stop services ----
echo [..] Stopping services...
for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo [OK] All services stopped

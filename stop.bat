@echo off
title AgentForge Stopper

cd /d "%~dp0"

echo =============================================
echo      AgentForge - Stop Services
echo =============================================
echo.

echo [..] Stopping AgentForge...

for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq node.exe" /fo csv /nh 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo [OK] All AgentForge services stopped
echo.
pause

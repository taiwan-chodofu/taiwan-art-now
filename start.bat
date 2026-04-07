@echo off
chcp 65001 >nul
echo ============================================
echo   Taiwan Art Exhibition Tracker
echo ============================================
echo.
echo   URL: http://127.0.0.1:5050
echo   Press Ctrl+C or close this window to stop
echo.
start http://127.0.0.1:5050
set PYTHONIOENCODING=utf-8
set PYTHONWARNINGS=ignore
py app.py 2>nul
pause

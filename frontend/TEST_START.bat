@echo off
chcp 65001 > nul
cd /d "E:\gov-support-automation\frontend"
echo.
echo ====================================
echo Starting FastAPI Server
echo ====================================
echo.
python app_safe.py
pause

@echo off
setlocal
cd /d "%~dp0"
python tools\upload_wokwi_micropython.py %*
exit /b %ERRORLEVEL%

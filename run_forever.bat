@echo off
cd "C:\Users\LENOVO\Desktop\linkdin projects"

:loop
echo ============================================
echo Starting NSE Monitor...
echo [%date% %time%] STARTED >> crashes.log

python nse_monitor.py
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] STOPPED (exit code: %EXIT_CODE%) >> crashes.log

if %EXIT_CODE%==0 (
    echo Script exited normally. Restarting in 10 seconds...
    echo [%date% %time%] Reason: Normal exit >> crashes.log
) else (
    echo Script CRASHED with exit code %EXIT_CODE%. Restarting in 10 seconds...
    echo [%date% %time%] Reason: CRASH (exit code %EXIT_CODE%) >> crashes.log
)

echo -------------------------------------------- >> crashes.log
timeout /t 10
goto loop

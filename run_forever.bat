@echo off
cd "C:\Users\LENOVO\Desktop\linkdin projects"

echo ============================================
echo Launching Telegram Bot in separate window...
echo ============================================
start "Telegram Bot" /min run_bot_forever.bat

timeout /t 3

:loop
echo ============================================
echo Starting NSE Monitor...
echo [%date% %time%] STARTED >> crashes.log

python nse_monitor.py
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] STOPPED (exit code: %EXIT_CODE%) >> crashes.log

if %EXIT_CODE%==0 (
    echo Script exited normally (Ctrl+C or clean stop).
    echo [%date% %time%] Reason: Normal exit >> crashes.log
    echo Restarting in 10 seconds...
) else (
    echo Script CRASHED with exit code %EXIT_CODE%. Restarting in 10 seconds...
    echo [%date% %time%] Reason: CRASH (exit code %EXIT_CODE%) >> crashes.log
    REM Send crash Telegram alert
    python -c "from dotenv import load_dotenv; load_dotenv(); import os, requests; t=os.environ.get('TELEGRAM_TOKEN',''); [requests.post(f'https://api.telegram.org/bot{t}/sendMessage', json={'chat_id':c.strip(),'text':'\u26a0\ufe0f NSE Monitor crashed! Restarting in 10 seconds...'}, timeout=10) for c in open('subscribers.txt').readlines() if c.strip()]" 2>nul
)

echo -------------------------------------------- >> crashes.log
timeout /t 10

REM Send restart Telegram alert
python -c "from dotenv import load_dotenv; load_dotenv(); import os, requests; t=os.environ.get('TELEGRAM_TOKEN',''); [requests.post(f'https://api.telegram.org/bot{t}/sendMessage', json={'chat_id':c.strip(),'text':'\u2705 NSE Monitor restarted successfully!'}, timeout=10) for c in open('subscribers.txt').readlines() if c.strip()]" 2>nul

goto loop

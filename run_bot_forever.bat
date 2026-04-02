@echo off
cd "C:\Users\LENOVO\Desktop\linkdin projects"

:loop
echo ============================================
echo Starting Telegram Bot...
echo [%date% %time%] BOT STARTED >> bot_crashes.log

python telegram_bot.py
set EXIT_CODE=%ERRORLEVEL%

echo [%date% %time%] BOT STOPPED (exit code: %EXIT_CODE%) >> bot_crashes.log

if %EXIT_CODE%==0 (
    echo Bot exited normally.
    echo [%date% %time%] Reason: Normal exit >> bot_crashes.log
    echo Restarting bot in 10 seconds...
) else (
    echo Bot CRASHED with exit code %EXIT_CODE%. Restarting in 10 seconds...
    echo [%date% %time%] Reason: CRASH (exit code %EXIT_CODE%) >> bot_crashes.log
    REM Send crash Telegram alert
    python -c "from dotenv import load_dotenv; load_dotenv(); import os, requests; t=os.environ.get('TELEGRAM_TOKEN',''); [requests.post(f'https://api.telegram.org/bot{t}/sendMessage', json={'chat_id':c.strip(),'text':'\u26a0\ufe0f Telegram Bot crashed! Restarting in 10 seconds...'}, timeout=10) for c in open('subscribers.txt').readlines() if c.strip()]" 2>nul
)

echo -------------------------------------------- >> bot_crashes.log
timeout /t 10

REM Send restart Telegram alert
python -c "from dotenv import load_dotenv; load_dotenv(); import os, requests; t=os.environ.get('TELEGRAM_TOKEN',''); [requests.post(f'https://api.telegram.org/bot{t}/sendMessage', json={'chat_id':c.strip(),'text':'\u2705 Telegram Bot restarted successfully!'}, timeout=10) for c in open('subscribers.txt').readlines() if c.strip()]" 2>nul

goto loop

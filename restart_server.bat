@echo off

echo Stopping server on port 8000...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F
)

timeout /t 2 /nobreak > nul

echo Starting Hair Research Database...

call C:\Users\Administrator\anaconda3\Scripts\activate.bat hair_database

cd /d D:\Database_for_human_hair_research

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
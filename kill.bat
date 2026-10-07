@echo off

echo Changing to project directory...

cd /d D:\Database_for_human_hair_research

echo Current directory:
cd

echo.
echo Looking for process using port 8000...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Killing PID %%a
    taskkill /PID %%a /F
)

echo.
echo Done.
pause
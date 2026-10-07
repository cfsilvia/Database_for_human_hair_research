@echo off

call C:\Users\Administrator\anaconda3\Scripts\activate.bat hair_database

cd /d D:\Database_for_human_hair_research

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
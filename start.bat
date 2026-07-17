@echo off
python check_os.py
if errorlevel 1 pause & exit /b 1
python ./main.py
@echo off
set ADMIN_ENROLLMENT_TOKEN=admin123
set CAMERA_BACKEND=opencv
set CAMERA_INDEX=0
set PYTHONIOENCODING=utf-8
"%USERPROFILE%\miniconda3\envs\face-access\python.exe" app.py
pause

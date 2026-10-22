# Run Real-Time Face Recognition (Generation 2 - SCRFD)
$env:CAMERA_BACKEND="opencv"
$env:CAMERA_INDEX="0"
$env:PYTHONIOENCODING="utf-8"

$pythonPath = "$env:USERPROFILE\miniconda3\envs\face-access\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Error "Could not find face-access environment at $pythonPath"
    exit 1
}

Write-Host "Starting Gen-2 SCRFD with Python 3.11 ($pythonPath)..." -ForegroundColor Cyan
& $pythonPath app.py

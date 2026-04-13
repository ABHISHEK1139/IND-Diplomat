@echo off
setlocal
cd /d %~dp0\..

if not exist diplomat_env\Scripts\python.exe (
  echo Creating virtual environment: diplomat_env
  python -m venv diplomat_env
  if errorlevel 1 (
    echo ERROR: failed to create virtual environment diplomat_env
    exit /b 1
  )
)

call diplomat_env\Scripts\activate
if errorlevel 1 (
  echo ERROR: failed to activate diplomat_env
  exit /b 1
)

python system_bootstrap\bootstrap.py %*
exit /b %errorlevel%

@echo off
setlocal
echo ===================================================
echo     IND-Diplomat 3.0 - Next-Gen Intelligence Engine
echo ===================================================
echo.
echo Please select how you want to run the system:
echo 1) Run Locally (Creates Virtual Environment ^& Installs Dependencies)
echo 2) Run via Docker (Builds and runs all microservices)
echo 3) Run tests locally
echo 4) Exit
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" goto local
if "%choice%"=="2" goto docker
if "%choice%"=="3" goto tests
goto end

:local
echo [INFO] Setting up local environment...
if not exist venv (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
echo [INFO] Installing dependencies...
pip install -r requirements.txt
pip install -e .
:run_server
echo [INFO] Starting the IND-Diplomat API Server (Auto-Heal enabled)...
python -m uvicorn dip.api:app --host 0.0.0.0 --port 8000
echo [WARNING] Server stopped or crashed! Auto-restarting in 5 seconds...
timeout /t 5 >nul
goto run_server

:docker
echo [INFO] Starting Docker Compose...
cd docker
docker-compose up --build
cd ..
goto end

:tests
echo [INFO] Running automated test suite...
if not exist venv (
    echo [ERROR] Virtual environment not found. Please run Option 1 first to install dependencies.
    goto end
)
call venv\Scripts\activate.bat
pytest tests/ -q
goto end

:end
echo Exiting...
endlocal
pause

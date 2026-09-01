@echo off
setlocal
echo ===================================================
echo     Politiq AI 3.0 - Ultimate 1-Click Starter
echo ===================================================
echo.

:: 1. API Keys & Configuration
if not exist ".env" (
    echo [INFO] No .env file found. Creating from .env.example...
    if exist ".env.example" (
        copy .env.example .env >nul
    ) else (
        echo LLM_MODEL=ollama/qwen3.5:4b > .env
        echo LLM_API_BASE=http://127.0.0.1:11434 >> .env
        echo OPENAI_API_KEY=your_openai_key >> .env
        echo TAVILY_API_KEY=your_tavily_key >> .env
    )
    echo.
    echo [ACTION REQUIRED] A new '.env' file has been created in the root directory.
    echo Please open '.env' and add your API keys (e.g. OPENAI_API_KEY, TAVILY_API_KEY^)
    echo if you are not using a local Ollama model.
    echo.
    echo Press any key to continue once your keys are ready...
    pause
)

:: 2. Backend Dependencies
echo [INFO] Setting up Python backend environment...
if not exist venv (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo [INFO] Installing Python dependencies (this may take a moment)...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt >nul
pip install -e . >nul

:: 3. Frontend Dependencies
echo [INFO] Setting up Node.js frontend environment...
if not exist "frontend-next\node_modules" (
    cd frontend-next
    echo [INFO] Installing NPM packages (this may take a moment)...
    call npm install
    cd ..
)

:: 4. Start Both Servers
echo [INFO] Starting Backend API on port 8000...
start "Politiq AI Backend" cmd /c "call venv\Scripts\activate.bat && python -m uvicorn dip.api:app --host 0.0.0.0 --port 8000"

echo [INFO] Starting Frontend UI on port 3000...
start "Politiq AI Frontend" cmd /c "cd frontend-next && npm run dev"

echo.
echo ===================================================
echo SUCCESS! System is starting up in separate windows.
echo - Backend API: http://localhost:8000
echo - Frontend UI: http://localhost:3000
echo ===================================================
echo Close this window when you are done to shut down.
pause

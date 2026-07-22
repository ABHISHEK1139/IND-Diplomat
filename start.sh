#!/bin/bash
echo "==================================================="
echo "    IND-Diplomat 3.0 - Next-Gen Intelligence Engine"
echo "==================================================="
echo ""
echo "Please select how you want to run the system:"
echo "1) Run Locally (Creates Virtual Environment & Installs Dependencies)"
echo "2) Run via Docker (Builds and runs all microservices)"
echo "3) Exit"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "[INFO] Setting up local environment..."
        if [ ! -d "venv" ]; then
            echo "[INFO] Creating Python virtual environment..."
            python3 -m venv venv
        fi
        source venv/bin/activate
        echo "[INFO] Upgrading pip..."
        pip install --upgrade pip
        echo "[INFO] Installing dependencies..."
        pip install -r requirements.txt
        pip install -e .
        echo "[INFO] Starting the IND-Diplomat API Server (Auto-Heal enabled)..."
        while true; do
            python -m uvicorn dip.api:app --host 0.0.0.0 --port 8000
            echo "[WARNING] Server stopped or crashed! Auto-restarting in 5 seconds..."
            sleep 5
        done
        ;;
    2)
        echo "[INFO] Starting Docker Compose..."
        cd docker
        docker-compose up --build
        cd ..
        ;;
    3)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice."
        ;;
esac

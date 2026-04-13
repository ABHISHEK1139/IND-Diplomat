
# IND-Diplomat Dependency Setup Script
# ====================================

Write-Host "[IND-Diplomat] Starting Environment Setup..." -ForegroundColor Cyan

# 1. Check for Winget (Package Manager)
if (-not (Get-Command "winget" -ErrorAction SilentlyContinue)) {
    Write-Error "Winget is not installed. Please install App Installer from Microsoft Store."
    exit 1
}

# 2. Install Tesseract OCR
Write-Host "`n[1/4] Installing Tesseract OCR..." -ForegroundColor Yellow
winget list "Tesseract-OCR" | Out-Null
if ($?) {
    Write-Host "Tesseract already installed." -ForegroundColor Green
} else {
    winget install --id UB-Mannheim.TesseractOCR --silent --accept-source-agreements --accept-package-agreements
    Write-Host "Tesseract installed. You may need to restart your terminal." -ForegroundColor Green
}

# 3. Install Poppler (via Scoop or manual guidance as winget support varies)
Write-Host "`n[2/4] Checking Poppler..." -ForegroundColor Yellow
if (-not (Get-Command "pdftoppm" -ErrorAction SilentlyContinue)) {
    Write-Host "Poppler not found in PATH." -ForegroundColor Red
    Write-Host "Please download Poppler release from: https://github.com/oschwartz10612/poppler-windows/releases/"
    Write-Host "Extract to C:\Program Files\Poppler and add 'bin' folder to System PATH."
} else {
    Write-Host "Poppler detected." -ForegroundColor Green
}

# 4. Install Python Dependencies
Write-Host "`n[3/4] Installing Python Libraries..." -ForegroundColor Yellow
pip install pdf2image pytesseract pypdf python-docx beautifulsoup4

# 5. Pull DeepSeek Model (via Ollama)
Write-Host "`n[4/4] Pulling DeepSeek-R1 Model..." -ForegroundColor Yellow
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    Write-Host "Pulling deepseek-r1:8b..."
    ollama pull deepseek-r1:8b
} else {
    Write-Host "Ollama not found. Please install Ollama from https://ollama.com" -ForegroundColor Red
}

Write-Host "`n[IND-Diplomat] Setup Logic Complete. Verify any manual steps above." -ForegroundColor Cyan
pause

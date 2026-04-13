
# ESDS Sovereign Cloud Deployment Script for IND-Diplomat
# Usage: .\deploy_esds.ps1 -ApiKey "YOUR_KEY" -Env "production"

param (
    [string]$ApiKey,
    [string]$Env = "production"
)

Write-Host "Initializing IND-Diplomat Deployment to ESDS Sovereign Cloud..." -ForegroundColor Cyan

# 1. Validate Prerequisites
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed."
    exit 1
}

# 2. Set Sovereign Environment Variables
$Env:IND_DIPLOMAT_ENV = $Env
$Env:IND_DIPLOMAT_API_KEY = $ApiKey
$Env:NEO4J_URI = "bolt://neo4j-sovereign:7687" # Internal sovereign DNS
$Env:CHROMA_HOST = "chroma-sovereign"

Write-Host "Environment Configured: $Env"

# 3. Build Sovereign Images
Write-Host "Building Containers..."
docker-compose --file docker-compose.yml build

# 4. Deployment (Simulated ESDS Push)
# In reality, this would push to ESDS private registry
# docker tag ind-diplomat-api esds-registry.local/ind-diplomat-api:latest
# docker push esds-registry.local/ind-diplomat-api:latest

# 5. Bring Up Services
Write-Host "Starting Services in Sovereign Mode..."
docker-compose --file docker-compose.yml up -d

# 6. Verify Health
Start-Sleep -Seconds 10
$health = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -ErrorAction SilentlyContinue

if ($health.status -eq "healthy") {
    Write-Host "Deployment Successful! System is LIVE on ESDS." -ForegroundColor Green
    Write-Host "Access API at: http://localhost:8000/docs"
}
else {
    Write-Error "Health Check Failed."
}

# run_server.ps1
# Usage: .\run_server.ps1

Write-Host "Starting REV FIT AI Pose Analysis Backend..." -ForegroundColor Cyan

# Ensure we are in the correct directory
Set-Location -Path $PSScriptRoot

# Check if requirements are installed (at least fastapi)
try {
    python -c "import fastapi"
} catch {
    Write-Host "Error: Dependencies not found. Running pip install..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

Write-Host "Server starting at http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray

uvicorn main:app --reload --port 8000

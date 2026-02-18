# CRM Backend - Environment Setup (PowerShell)
# Run this script to set up your development environment

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CRM Backend - Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "[1/5] Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host $pythonVersion -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Navigate to backend directory
Set-Location backend

# Create virtual environment
Write-Host ""
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists. Skipping creation." -ForegroundColor Green
} else {
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "Virtual environment created successfully!" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "[3/5] Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "You may need to run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Install dependencies
Write-Host ""
Write-Host "[4/5] Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Dependencies installed successfully!" -ForegroundColor Green

# Create .env file
Write-Host ""
Write-Host "[5/5] Creating .env file..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host ".env file already exists. Skipping creation." -ForegroundColor Green
} else {
    Copy-Item .env.example .env
    Write-Host ".env file created from template!" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: Please edit backend\.env and configure:" -ForegroundColor Yellow
    Write-Host "  - DB_NAME=crm_backend" -ForegroundColor White
    Write-Host "  - DB_USER=your_postgres_username" -ForegroundColor White
    Write-Host "  - DB_PASSWORD=your_postgres_password" -ForegroundColor White
    Write-Host "  - SECRET_KEY=generate-a-50-character-random-string" -ForegroundColor White
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Environment Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Edit backend\.env file with your database credentials" -ForegroundColor White
Write-Host ""
Write-Host "2. Create PostgreSQL database:" -ForegroundColor White
Write-Host "   Option A: Using psql command line" -ForegroundColor Gray
Write-Host "     createdb crm_backend" -ForegroundColor Gray
Write-Host ""
Write-Host "   Option B: Using pgAdmin GUI" -ForegroundColor Gray
Write-Host "     - Right-click Databases > Create > Database" -ForegroundColor Gray
Write-Host "     - Name: crm_backend" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Run migrations:" -ForegroundColor White
Write-Host "   cd backend" -ForegroundColor Gray
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "   python manage.py migrate" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Create superuser:" -ForegroundColor White
Write-Host "   python manage.py createsuperuser" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Start development server:" -ForegroundColor White
Write-Host "   python manage.py runserver" -ForegroundColor Gray
Write-Host ""
Write-Host "6. Access API documentation:" -ForegroundColor White
Write-Host "   http://localhost:8000/api/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"

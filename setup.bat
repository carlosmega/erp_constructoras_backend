@echo off
echo ========================================
echo CRM Backend - Environment Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Checking Python version...
python --version

echo.
echo [2/5] Creating virtual environment...
cd backend
if exist venv (
    echo Virtual environment already exists. Skipping creation.
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
)

echo.
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo.
echo [4/5] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [5/5] Creating .env file...
if exist .env (
    echo .env file already exists. Skipping creation.
) else (
    copy .env.example .env
    echo .env file created from template!
    echo.
    echo IMPORTANT: Please edit backend\.env and configure:
    echo   - DB_NAME=crm_backend
    echo   - DB_USER=your_postgres_username
    echo   - DB_PASSWORD=your_postgres_password
    echo   - SECRET_KEY=generate-a-50-character-random-string
)

echo.
echo ========================================
echo Environment Setup Complete!
echo ========================================
echo.
echo NEXT STEPS:
echo.
echo 1. Edit backend\.env file with your database credentials
echo.
echo 2. Create PostgreSQL database:
echo    Option A: Using psql command line
echo      createdb crm_backend
echo.
echo    Option B: Using pgAdmin GUI
echo      - Right-click Databases ^> Create ^> Database
echo      - Name: crm_backend
echo.
echo 3. Run migrations:
echo    cd backend
echo    venv\Scripts\activate
echo    python manage.py migrate
echo.
echo 4. Create superuser:
echo    python manage.py createsuperuser
echo.
echo 5. Start development server:
echo    python manage.py runserver
echo.
echo 6. Access API documentation:
echo    http://localhost:8000/api/docs
echo.
echo ========================================
echo.
pause

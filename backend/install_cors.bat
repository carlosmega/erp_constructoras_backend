@echo off
echo ========================================
echo Instalando django-cors-headers en venv
echo ========================================
echo.

cd /d "%~dp0"

echo Verificando entorno virtual...
if not exist "venv\Scripts\python.exe" (
    echo ERROR: No se encontro el entorno virtual en venv\
    echo Por favor ejecuta setup.bat primero
    pause
    exit /b 1
)

echo Instalando django-cors-headers...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install django-cors-headers==4.3.1

echo.
echo Verificando instalacion...
venv\Scripts\python.exe -m pip show django-cors-headers

echo.
echo ========================================
echo Instalacion completada!
echo ========================================
echo.
echo Ahora puedes ejecutar: python manage.py runserver
echo.
pause

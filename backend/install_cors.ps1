# Script de instalación de django-cors-headers para PowerShell
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Instalando django-cors-headers en venv" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "Verificando entorno virtual..." -ForegroundColor Yellow
if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "ERROR: No se encontró el entorno virtual en venv\" -ForegroundColor Red
    Write-Host "Por favor ejecuta setup.ps1 primero" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "Instalando django-cors-headers..." -ForegroundColor Green
& venv\Scripts\python.exe -m pip install --upgrade pip
& venv\Scripts\python.exe -m pip install django-cors-headers==4.3.1

Write-Host ""
Write-Host "Verificando instalación..." -ForegroundColor Yellow
& venv\Scripts\python.exe -m pip show django-cors-headers

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Instalación completada!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Ahora puedes ejecutar: python manage.py runserver" -ForegroundColor Yellow
Write-Host ""
Read-Host "Presiona Enter para continuar"

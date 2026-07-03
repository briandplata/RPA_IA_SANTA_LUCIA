@echo off
title LUCIA - RPA IA Santa Lucia IPS
cd /d "%~dp0"

echo.
echo  ==========================================
echo   LUCIA - RPA IA Santa Lucia IPS S.A.S.
echo  ==========================================
echo.

:: Verificar que uv este instalado
where uv >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] uv no esta instalado.
    echo  Ejecute primero el archivo INSTALAR_LUCIA.bat
    echo.
    pause
    exit /b 1
)

:: Verificar que .env exista
if not exist ".env" (
    echo  [ERROR] No se encontro el archivo .env con las credenciales.
    echo  Cree el archivo .env con sus datos antes de continuar.
    echo.
    pause
    exit /b 1
)

echo  Iniciando robot... por favor espere.
echo.

uv run python main.py

echo.
if errorlevel 1 (
    echo  [!] El robot finalizo con errores. Revise la carpeta logs\
) else (
    echo  Robot finalizado correctamente.
)
echo.
pause

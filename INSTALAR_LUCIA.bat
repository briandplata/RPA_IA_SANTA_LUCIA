@echo off
title LUCIA - Instalacion
cd /d "%~dp0"

echo.
echo  ==========================================
echo   LUCIA - Instalacion inicial
echo   RPA IA Santa Lucia IPS S.A.S.
echo  ==========================================
echo.

:: ── 1. Verificar/instalar uv ──────────────────────────────────
where uv >nul 2>&1
if errorlevel 1 (
    echo  [1/4] Instalando uv...
    winget install astral-sh.uv --silent
    if errorlevel 1 (
        echo  [ERROR] No se pudo instalar uv automaticamente.
        echo  Instale manualmente desde: https://docs.astral.sh/uv/
        pause
        exit /b 1
    )
    echo  uv instalado correctamente.
) else (
    echo  [1/4] uv ya esta instalado. OK
)

:: ── 2. Instalar dependencias del proyecto ────────────────────
echo.
echo  [2/4] Instalando dependencias Python...
uv sync
if errorlevel 1 (
    echo  [ERROR] Fallo la instalacion de dependencias.
    pause
    exit /b 1
)
echo  Dependencias instaladas. OK

:: ── 3. Instalar navegador Playwright (Chromium) ──────────────
echo.
echo  [3/4] Instalando navegador Chromium para Playwright...
uv run playwright install chromium
if errorlevel 1 (
    echo  [ERROR] Fallo la instalacion de Chromium.
    pause
    exit /b 1
)
echo  Chromium instalado. OK

:: ── 4. Crear estructura de carpetas ─────────────────────────
echo.
echo  [4/4] Creando estructura de carpetas...
if not exist "pacientes\pendientes"      mkdir "pacientes\pendientes"
if not exist "pacientes\procesados"      mkdir "pacientes\procesados"
if not exist "pacientes\no_procesados"   mkdir "pacientes\no_procesados"
if not exist "logs"                      mkdir "logs"
if not exist "output"                    mkdir "output"
echo  Carpetas creadas. OK

:: ── Crear .env si no existe ──────────────────────────────────
if not exist ".env" (
    echo.
    echo  Creando archivo .env de ejemplo...
    (
        echo OPENAI_API_KEY=sk-PONGA_SU_CLAVE_AQUI
        echo WEB_USER=su_usuario_saludtotal
        echo WEB_PASSWORD=su_contrasena_saludtotal
    ) > .env
    echo  IMPORTANTE: Edite el archivo .env con sus credenciales reales.
)

echo.
echo  ==========================================
echo   Instalacion completada exitosamente.
echo  ==========================================
echo.
echo  PROXIMOS PASOS:
echo   1. Edite el archivo .env con sus credenciales reales
echo   2. Copie los PDFs a la carpeta: pacientes\pendientes\
echo   3. Ejecute EJECUTAR_LUCIA.bat para iniciar el robot
echo.
pause

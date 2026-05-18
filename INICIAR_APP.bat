@echo off
title BYD Ads Scraper
color 0A
cd /d "%~dp0"

echo.
echo  ============================================
echo   BYD Costa Rica - Facebook Ads Scraper
echo  ============================================
echo.

:: ── 1. Verificar Python ───────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python no esta instalado.
    echo.
    echo  Descargalo de: https://python.org/downloads
    echo  Marca "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo  Python: %%i

:: ── 2. Instalar dependencias ──────────────────────────────────────────────
echo.
echo  [1/3] Instalando dependencias de Python...
pip install playwright openpyxl pillow requests --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  [ERROR] Fallo pip install. Corre este .bat como Administrador.
    pause
    exit /b 1
)
echo        OK

:: ── 3. Instalar Chromium (navegador headless) ─────────────────────────────
echo.
echo  [2/3] Instalando navegador Chromium (solo la primera vez, ~150 MB)...
python -m playwright install chromium --with-deps >nul 2>&1
if errorlevel 1 (
    python -m playwright install chromium
)
echo        OK

:: ── 4. Correr el scraper ──────────────────────────────────────────────────
echo.
echo  [3/3] Iniciando scraper de BYD Costa Rica...
echo.
echo  Se abrira un navegador invisible que recorre la Biblioteca de Anuncios.
echo  Al terminar encontraras el Excel en la carpeta byd_ads_output\
echo.
echo  ============================================
echo.

python byd_scraper.py %*

echo.
echo  ============================================
echo   Listo! Abre la carpeta byd_ads_output\
echo  ============================================
echo.

:: Abrir carpeta con el resultado
if exist byd_ads_output (
    explorer byd_ads_output
)

pause

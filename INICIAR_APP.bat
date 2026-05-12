@echo off
title BYD Ads Intelligence - Instalando y lanzando...
color 0A

echo.
echo  ██████╗ ██╗   ██╗██████╗
echo  ██╔══██╗╚██╗ ██╔╝██╔══██╗
echo  ██████╔╝ ╚████╔╝ ██║  ██║
echo  ██╔══██╗  ╚██╔╝  ██║  ██║
echo  ██████╔╝   ██║   ██████╔╝
echo  ╚═════╝    ╚═╝   ╚═════╝
echo.
echo  BYD Costa Rica - Ads Intelligence
echo  ====================================
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python no esta instalado.
    echo.
    echo  Descargalo de: https://python.org/downloads
    echo  Asegurate de marcar "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo  [1/3] Python encontrado. Instalando dependencias...
echo.
pip install streamlit plotly pandas pillow openpyxl requests --quiet

if errorlevel 1 (
    echo.
    echo  [ERROR] Fallo la instalacion. Intenta correr como Administrador.
    pause
    exit /b 1
)

echo.
echo  [2/3] Dependencias instaladas OK.
echo.
echo  [3/3] Lanzando la app en http://localhost:8501 ...
echo.
echo  (Cierra esta ventana para detener la app)
echo.

:: Ir al directorio donde esta este .bat
cd /d "%~dp0"

streamlit run byd_ads_app.py --server.enableCORS false --server.enableXsrfProtection false

pause

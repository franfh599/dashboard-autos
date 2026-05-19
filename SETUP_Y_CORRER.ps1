# BYD Costa Rica - Setup y Scraper Automatico
# Pega este script completo en PowerShell y presiona Enter
# Hace todo solo: instala Python, dependencias y corre el scraper

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  BYD Costa Rica - Facebook Ads Scraper" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Verificar / instalar Python ──────────────────────────────────────────
Write-Host "[1/5] Verificando Python..." -ForegroundColor Yellow

$pythonOk = $false
try {
    $ver = python --version 2>&1
    if ($ver -match "Python 3") {
        Write-Host "      Python OK: $ver" -ForegroundColor Green
        $pythonOk = $true
    }
} catch {}

if (-not $pythonOk) {
    Write-Host "      Python no encontrado. Instalando con winget..." -ForegroundColor Yellow
    winget install --id Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Start-Sleep -Seconds 3
    $ver = python --version 2>&1
    Write-Host "      Instalado: $ver" -ForegroundColor Green
}

# ── 2. Clonar o actualizar repositorio ───────────────────────────────────────
Write-Host ""
Write-Host "[2/5] Obteniendo el codigo..." -ForegroundColor Yellow

$repoPath = "$env:USERPROFILE\dashboard-autos"

if (Test-Path $repoPath) {
    Write-Host "      Carpeta ya existe, actualizando..." -ForegroundColor Yellow
    Set-Location $repoPath
    git pull origin claude/byd-ads-scraper-IXh5U 2>&1 | Out-Null
} else {
    # Check if git is available
    $gitOk = $null -ne (Get-Command git -ErrorAction SilentlyContinue)
    if (-not $gitOk) {
        Write-Host "      Instalando Git..." -ForegroundColor Yellow
        winget install --id Git.Git --source winget --silent --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }
    Write-Host "      Clonando repositorio..." -ForegroundColor Yellow
    git clone https://github.com/franfh599/dashboard-autos.git $repoPath 2>&1 | Out-Null
    Set-Location $repoPath
    git checkout claude/byd-ads-scraper-IXh5U 2>&1 | Out-Null
}

Write-Host "      Codigo listo en: $repoPath" -ForegroundColor Green

# ── 3. Instalar dependencias Python ──────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] Instalando dependencias de Python..." -ForegroundColor Yellow

python -m pip install --upgrade pip --quiet
python -m pip install playwright openpyxl pillow requests --quiet

Write-Host "      Dependencias OK" -ForegroundColor Green

# ── 4. Instalar Chromium (navegador headless) ─────────────────────────────────
Write-Host ""
Write-Host "[4/5] Instalando navegador Chromium para el scraper..." -ForegroundColor Yellow
Write-Host "      (Solo la primera vez, puede tardar 2-3 minutos)" -ForegroundColor Gray

python -m playwright install chromium --with-deps 2>&1 | Out-Null

Write-Host "      Chromium OK" -ForegroundColor Green

# ── 5. Correr el scraper ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Iniciando scraper de BYD Costa Rica..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Raspa los anuncios activos de BYD CR en Facebook Ads Library." -ForegroundColor Gray
Write-Host "  Al terminar se abre automaticamente la carpeta con el Excel." -ForegroundColor Gray
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $repoPath
python byd_scraper.py --max 200

# ── Abrir carpeta resultado ───────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Listo! Abriendo carpeta de resultados..." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$outputPath = Join-Path $repoPath "byd_ads_output"
if (Test-Path $outputPath) {
    explorer $outputPath
}

Write-Host "Presiona cualquier tecla para cerrar..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

param(
    [switch]$Console
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$assets = Join-Path $root "assets"
$icon = Join-Path $assets "kick.ico"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creando entorno virtual en $venv"
    py -m venv $venv
}

Write-Host "Instalando dependencias"
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Fallo la actualizacion de pip" }
& $python -m pip install -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de dependencias" }
& $python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de PyInstaller" }

Write-Host "Generando icono"
Push-Location $root
try {
    & $python "icon.py" "assets\kick.ico"
    if ($LASTEXITCODE -ne 0) { throw "Fallo la generacion del icono" }
}
finally {
    Pop-Location
}

$name = if ($Console) { "KickPresence-console" } else { "KickPresence" }
$mode = if ($Console) { "--console" } else { "--windowed" }

$pyArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--name", $name,
    "--icon", $icon,
    "--hidden-import", "pystray._win32",
    "--hidden-import", "icon",
    "--hidden-import", "tkinter",
    "--hidden-import", "tkinter.ttk",
    "--hidden-import", "PIL._tkinter_finder",
    $mode,
    "--distpath", (Join-Path $root "dist"),
    "--workpath", (Join-Path $root "build"),
    "--specpath", (Join-Path $root "build")
)

$iconNames = @(
    "rika-icon.jpg", "rika-icon.jpeg", "rika-icon.png", "rika-icon.webp",
    "icon-source.png", "icon-source.jpg", "icon-source.webp",
    "homura.png", "homura.jpg", "homura.jpeg", "homura.webp",
    "kick-homu.png", "custom.png", "custom.jpg", "custom.webp"
)

foreach ($candidate in $iconNames) {
    $path = Join-Path $assets $candidate
    if (Test-Path -LiteralPath $path) {
        Write-Host "Incluyendo imagen: $candidate"
        $pyArgs += @("--add-data", "$path;assets")
        break
    }
}

$pyArgs += (Join-Path $root "main.py")

Write-Host "Compilando $name.exe"
$running = Get-Process KickPresence -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Cerrando KickPresence para poder sobrescribir el .exe"
    $running | Stop-Process -Force
    Start-Sleep -Seconds 2
}
& $python @pyArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo con codigo $LASTEXITCODE" }

Write-Host "Listo: $(Join-Path $root "dist\$name.exe")"

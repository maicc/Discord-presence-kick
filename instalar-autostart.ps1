param(
    [switch]$Quitar
)

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "KickPresence.lnk"

if ($Quitar) {
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force
        Write-Host "Inicio automatico desactivado"
    }
    else {
        Write-Host "El inicio automatico no estaba activado"
    }
    exit 0
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $root "KickPresence.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    $exe = Join-Path $root "dist\KickPresence.exe"
}
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Host "No se encontro KickPresence.exe (buscalo junto a este script o en dist\)"
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = Split-Path -Parent $exe
$shortcut.Description = "Muestra en Discord cuando tu canal de Kick esta en vivo"
$shortcut.Save()

Write-Host "Inicio automatico activado"
Write-Host "Acceso directo: $shortcutPath"
Write-Host "Para desactivarlo: .\instalar-autostart.ps1 -Quitar"

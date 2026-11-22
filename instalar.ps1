# Instala NetLab (antes Lab CCNA): acceso directo en el Escritorio y en el menu Inicio (Ctrl+Alt+L),
# y descarga la extension PTBuilder para que Packet Tracer pueda armar las practicas solo.
Set-Location $PSScriptRoot

$candidatos = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\pythonw.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\pythonw.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\pythonw.exe')
)
$pythonw = $candidatos | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonw) { $pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source }
if (-not $pythonw) { Write-Host 'No encontre Python 3.11+ (pythonw.exe).' -ForegroundColor Red; exit 1 }

$shell = New-Object -ComObject WScript.Shell
function Crear-Atajo($ruta, $teclas) {
    $a = $shell.CreateShortcut($ruta)
    $a.TargetPath = $pythonw                         # sin ventana de consola
    $a.Arguments = "-B `"$(Join-Path $PSScriptRoot 'app.py')`""
    $a.WorkingDirectory = $PSScriptRoot
    $a.IconLocation = (Join-Path $PSScriptRoot 'web\icono.ico')
    $a.Description = 'Packet Tracer, CCNA y Wireshark con IA local'
    if ($teclas) { $a.Hotkey = $teclas }
    $a.Save()
}
# Nombre nuevo: quita los accesos viejos 'Lab CCNA' (la carpeta se queda igual para no romper PTBuilder ni los .pkt)
foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $viejo = Join-Path $d 'Lab CCNA.lnk'
    if (Test-Path $viejo) { Remove-Item $viejo }
}
Crear-Atajo (Join-Path ([Environment]::GetFolderPath('Desktop')) 'NetLab.lnk') $null
Crear-Atajo (Join-Path ([Environment]::GetFolderPath('Programs')) 'NetLab.lnk') 'CTRL+ALT+L'
Write-Host 'Accesos directos NetLab listos: Escritorio y menu Inicio (Ctrl+Alt+L).' -ForegroundColor Green

# --- PTBuilder (extension de Packet Tracer, codigo abierto: github.com/kimmknight/PTBuilder) ---
$carpeta = Join-Path $PSScriptRoot 'extension'
New-Item -ItemType Directory -Force $carpeta | Out-Null
$pts = Join-Path $carpeta 'Builder.pts'
try {
    Invoke-WebRequest 'https://github.com/kimmknight/PTBuilder/raw/main/Builder.pts' -OutFile $pts -UseBasicParsing
    Write-Host "PTBuilder descargado en: $pts" -ForegroundColor Green
    Write-Host ''
    Write-Host 'Ultimo paso (una sola vez) en Packet Tracer:'
    Write-Host '  Extensions > Scripting > Configure PT Script Modules > Add...  y elige ese Builder.pts'
    Write-Host '  Luego aparece Extensions > Builder Code Editor.'
} catch {
    Write-Host 'No pude descargar PTBuilder. Bajalo a mano de github.com/kimmknight/PTBuilder (Builder.pts).' -ForegroundColor Yellow
}

# Hace que Packet Tracer abra SIEMPRE con la escala de NetLab (Ajustes -> Tamano de Packet Tracer):
#  - doble clic en archivos .pkt y .pka
#  - tus accesos directos de Packet Tracer (Escritorio y menu Inicio)
# Solo cambia tu usuario y solo esos archivos; no toca ningun otro programa.
# Para deshacerlo:  powershell -ExecutionPolicy Bypass -File .\asociar_pkt.ps1 -Quitar
param([switch]$Quitar)
Set-Location $PSScriptRoot

$pythonw = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\pythonw.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\pythonw.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\pythonw.exe')
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonw) { $pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source }
if (-not $pythonw) { Write-Host 'No encontre pythonw.exe' -ForegroundColor Red; exit 1 }

$lanzador = Join-Path $PSScriptRoot 'abrir_pt.pyw'
$comando = "`"$pythonw`" -B `"$lanzador`" `"%1`""

foreach ($ext in '.pkt', '.pka') {
    # El tipo de archivo que Windows usa hoy para esa extension (lo que elegiste o lo que dejo el instalador)
    $progId = $null
    $uc = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$ext\UserChoice"
    if (Test-Path $uc) { $progId = (Get-ItemProperty $uc -ErrorAction SilentlyContinue).ProgId }
    if (-not $progId) { $progId = (Get-Item "Registry::HKEY_CLASSES_ROOT\$ext" -ErrorAction SilentlyContinue).GetValue('') }
    if (-not $progId) { $progId = "LabCCNA$($ext.TrimStart('.'))"; New-Item "HKCU:\Software\Classes\$ext" -Force | Set-Item -Value $progId }

    $clave = "HKCU:\Software\Classes\$progId\shell\open\command"
    if ($Quitar) {
        if (Test-Path $clave) { Remove-Item $clave -Force; Write-Host "$ext vuelve a abrir normal." -ForegroundColor Green }
        continue
    }
    New-Item $clave -Force | Out-Null
    Set-Item $clave -Value $comando
    Write-Host "$ext ($progId): doble clic abre con la escala de NetLab." -ForegroundColor Green
}

# --- Accesos directos de Packet Tracer: que usen el mismo lanzador (sin ventana de consola) ---
if (-not $Quitar) {
    $exe = 'C:\Program Files\Cisco Packet Tracer 9.0.1\bin\PacketTracer.exe'
    $shell = New-Object -ComObject WScript.Shell
    foreach ($c in [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'),
                   [Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('CommonPrograms')) {
        Get-ChildItem $c -Filter *.lnk -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
            $a = $shell.CreateShortcut($_.FullName)
            if ($a.TargetPath -like '*PacketTracer.exe' -or $a.Arguments -like '*QT_SCALE_FACTOR*') {
                $a.TargetPath = $pythonw
                $a.Arguments = "-B `"$lanzador`""
                $a.IconLocation = "$exe,0"
                $a.WindowStyle = 1
                try { $a.Save(); Write-Host "Acceso directo listo: $($_.Name)" -ForegroundColor Green }
                catch { Write-Host "Sin permiso (abre PowerShell como administrador): $($_.FullName)" -ForegroundColor Yellow }
            }
        }
    }
}

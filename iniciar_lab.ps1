# Abre NetLab (lo mismo que el acceso directo). Si ya estaba abierto, solo trae la ventana.
Set-Location $PSScriptRoot
$pythonw = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\pythonw.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\pythonw.exe')
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonw) { $pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source }
Start-Process $pythonw -ArgumentList "-B `"$(Join-Path $PSScriptRoot 'app.py')`"" -WorkingDirectory $PSScriptRoot

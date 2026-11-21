# Mesa local de 5 jugadores con las condiciones de la clasificatoria (una ronda de 50 manos).
# Uso, desde cualquier carpeta:
#   powershell -ExecutionPolicy Bypass -File "<ruta>\bender\pruebas\mesa_demo.ps1"
$raiz = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $raiz

# Ventana 1: la mesa (queda abierta al final para ver las posiciones)
$mesa = "Set-Location '$raiz'; .\bin\mesa.exe -addr :9000 -jugadores 6 -min-jugadores 5 -rondas 50 -stack 10000 -ciega-chica 50 -ciega-grande 100 -timeout-ms 5000"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $mesa
Start-Sleep -Seconds 2

# Rivales del kit, en ventanas minimizadas
$rivales = @(@('base','rival-1'), @('espia','rival-2'), @('estadistico','rival-3'), @('bandido','rival-4'))
foreach ($r in $rivales) {
    Start-Process -WindowStyle Minimized -FilePath "$raiz\bin\$($r[0]).exe" -ArgumentList '-addr', 'localhost:9000', '-token', $r[1]
}

# Bender en esta ventana (token local cualquiera; NO usa el token real)
Write-Host "Bender conectándose a la mesa local..."
& "$raiz\bender\.venv\Scripts\python.exe" "$raiz\bender\main.py" -addr localhost:9000 -token bender
Write-Host "Listo. Las posiciones finales están en la ventana de la mesa. Las decisiones de Bender, en bender\logs\."

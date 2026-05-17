# Start API on ALL interfaces so phones on Wi-Fi can connect (Expo Go / dev build).
# If you only use: uvicorn ... --host 127.0.0.1  →  mobile will NEVER work.
Set-Location $PSScriptRoot

$port = 8000
$listeners = netstat -ano | Select-String ":$port\s" | Select-String "LISTENING"

foreach ($line in $listeners) {
  if ($line -match "127\.0\.0\.1:$port") {
    if ($line -match "\s+(\d+)\s*$") {
      $procId = [int]$Matches[1]
      Write-Host "Stopping old API on 127.0.0.1:$port (PID $procId) — phones cannot use localhost-only binding."
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 2
    }
  }
}

Write-Host ""
Write-Host "Starting VTailor API on http://0.0.0.0:$port"
Write-Host "Phone URL (set in app-vTailor/.env):"
Write-Host "  EXPO_PUBLIC_API_BASE_URL=http://192.168.1.6:$port/app/api/v1"
Write-Host ""
Write-Host "Test on PC browser: http://192.168.1.6:$port/docs"
Write-Host "If that fails, allow port $port in Windows Firewall (Private network)."
Write-Host ""

uvicorn app.main:app --host 0.0.0.0 --port $port --reload

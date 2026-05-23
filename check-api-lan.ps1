# Quick check: can this PC (and your phone) reach the API on Wi-Fi?
$port = 8000
$lanIp = (
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -match '^192\.168\.1\.\d+$' -and $_.PrefixOrigin -ne 'WellKnown' } |
    Select-Object -First 1 -ExpandProperty IPAddress
)
if (-not $lanIp) { $lanIp = '192.168.1.6' }

Write-Host "LAN IP: $lanIp"
Write-Host "Listeners on port ${port}:"
Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Write-Host "  $($_.LocalAddress):${port} PID $($_.OwningProcess)" }

$hasAll = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalAddress -eq '0.0.0.0' }
if (-not $hasAll) {
  Write-Host ""
  Write-Host "FAIL: API is not bound to 0.0.0.0. Phones cannot connect." -ForegroundColor Red
  Write-Host "Run: .\start-api.ps1"
  exit 1
}

try {
  $health = Invoke-WebRequest -Uri "http://${lanIp}:${port}/health" -UseBasicParsing -TimeoutSec 8
  Write-Host ""
  Write-Host "OK: http://${lanIp}:${port}/health -> $($health.Content)" -ForegroundColor Green
  Write-Host "Set EXPO_PUBLIC_API_BASE_URL=http://${lanIp}:${port}/app/api/v1"
  exit 0
} catch {
  Write-Host ""
  Write-Host "FAIL: http://${lanIp}:${port}/health -> $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Check Windows Firewall (Private) and run .\start-api.ps1"
  exit 1
}

# Start API on ALL interfaces so phones on Wi-Fi can connect (Expo Go / dev build).
# If you only use: uvicorn ... --host 127.0.0.1  →  mobile will NEVER work.
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
  Write-Host "ERROR: Missing Folder\.env" -ForegroundColor Red
  Write-Host "  1) copy .env.example to .env"
  Write-Host "  2) set JWT_SECRET_KEY, MONGODB_URL, MONGO_DB_NAME, STYTCH_PROJECT_ID, STYTCH_SECRET"
  Write-Host "  See AUTH_SECURITY_IMPLEMENTATION.md for details."
  exit 1
}

Write-Host "Checking Python dependencies..."
python -c "from app.main import app" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Installing requirements (first time or missing stream-chat)..."
  pip install -r requirements.txt
  python -c "from app.main import app"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backend import failed. Read the Python error above." -ForegroundColor Red
    exit 1
  }
}
Write-Host "Backend import OK."

$port = 8000

function Get-LanIpv4 {
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
      $_.IPAddress -match '^192\.168\.\d+\.\d+$' -and
      $_.PrefixOrigin -ne 'WellKnown'
    } |
    Sort-Object { if ($_.IPAddress -match '^192\.168\.1\.') { 0 } else { 1 } } |
    Select-Object -First 1 -ExpandProperty IPAddress
}

$lanIp = Get-LanIpv4
if (-not $lanIp) { $lanIp = '192.168.1.6' }

Write-Host "Stopping any process listening on port $port (localhost-only blocks phones)..."
for ($attempt = 1; $attempt -le 3; $attempt++) {
  $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
  if ($listeners.Count -eq 0) { break }
  foreach ($conn in $listeners) {
    $procId = $conn.OwningProcess
    if ($procId -and $procId -gt 0) {
      Write-Host "  Stopping PID $procId ($($conn.LocalAddress):$port)"
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
  }
  Start-Sleep -Seconds 2
}
$stillListening = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
if ($stillListening.Count -gt 0) {
  Write-Host "WARNING: Port $port still in use. Close other terminals running uvicorn, then run this script again." -ForegroundColor Yellow
  $stillListening | ForEach-Object { Write-Host "  Still listening: $($_.LocalAddress):$port PID $($_.OwningProcess)" }
}

# Allow inbound TCP 8000 from phones on Wi-Fi (Private AND Public profile — many PCs use Public on Wi-Fi)
$fwRule = 'VTailor API TCP 8000'
Write-Host "Ensuring Windows Firewall allows inbound TCP $port (all profiles)..."
netsh advfirewall firewall delete rule name="$fwRule" 2>$null | Out-Null
netsh advfirewall firewall add rule name="$fwRule" dir=in action=allow protocol=TCP localport=$port enable=yes | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Could not add firewall rule. Run PowerShell as Administrator once." -ForegroundColor Yellow
} else {
  Write-Host "Firewall rule added for TCP $port."
}

Write-Host ""
Write-Host "Starting VTailor API on http://0.0.0.0:$port"
Write-Host "Set in app-vTailor/.env:"
Write-Host "  EXPO_PUBLIC_API_BASE_URL=http://${lanIp}:$port/app/api/v1"
Write-Host ""
Write-Host "Test on PC browser: http://${lanIp}:$port/docs"
Write-Host "Test health:        http://${lanIp}:$port/health"
Write-Host ""

# --reload-dir app: stable on Windows; .env loaded from Folder via app/core/config.py
python -m uvicorn app.main:app --host 0.0.0.0 --port $port --reload --reload-dir app

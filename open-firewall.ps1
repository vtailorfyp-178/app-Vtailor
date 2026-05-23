# Run once as Administrator (right-click PowerShell → Run as administrator):
#   cd app-Vtailor
#   .\open-firewall.ps1
$port = 8000
$fwRule = 'VTailor API TCP 8000'
Write-Host "Adding firewall inbound rule for TCP $port (all profiles)..."
netsh advfirewall firewall delete rule name="$fwRule" 2>$null | Out-Null
netsh advfirewall firewall add rule name="$fwRule" dir=in action=allow protocol=TCP localport=$port enable=yes
if ($LASTEXITCODE -eq 0) {
  Write-Host "Done. Phones on Wi-Fi can reach http://YOUR_PC_IP:$port" -ForegroundColor Green
} else {
  Write-Host "Failed. Run this script as Administrator." -ForegroundColor Red
  exit 1
}

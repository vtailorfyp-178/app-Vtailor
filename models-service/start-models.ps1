# Start Cloudinary models API on port 3001 (serves GET /models from uploadResults.json or MongoDB).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Starting models-service on http://127.0.0.1:3001"
Write-Host "Web Expo: Metro proxies http://localhost:8081/models -> :3001"
Write-Host "Phone: set EXPO_PUBLIC_MODELS_API_URL=http://YOUR_PC_IP:3001 in app-vTailor/.env"
Write-Host ""

npm start

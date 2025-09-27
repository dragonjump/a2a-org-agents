$ErrorActionPreference = 'Stop'
Push-Location "$PSScriptRoot\..\frontend"
if (Test-Path node_modules) {
  Write-Host 'node_modules exists'
} else {
  npm install | Out-Host
}
npm run dev
Pop-Location


Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "All python processes killed"

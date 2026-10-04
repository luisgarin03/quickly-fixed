$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
docker compose -f docker-compose.local.yml up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop, then retry.' }
New-Item -ItemType Directory -Force "$repo\logs" | Out-Null
$python = "$repo\.venv\Scripts\python.exe"
foreach ($port in @(8000, 7000)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop the existing server before starting another."
    }
}
$backend = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload', '--reload-dir', 'app', '--timeout-graceful-shutdown', '5') -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput "$repo\logs\backend.out.log" -RedirectStandardError "$repo\logs\backend.err.log"
$node = (Get-Command node.exe).Source
$frontend = Start-Process -FilePath $node -ArgumentList @('node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '7000', '--strictPort') -WorkingDirectory "$repo\frontend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$repo\logs\frontend.out.log" -RedirectStandardError "$repo\logs\frontend.err.log"
Write-Host "Backend PID: $($backend.Id); frontend PID: $($frontend.Id)"
Write-Host 'UI: http://127.0.0.1:7000 | API/docs: http://127.0.0.1:8000/docs'
Write-Host 'Logs: C:\Apps\Quickly\logs. Test mode defaults on in .env; do not add real mailbox credentials for simulated tests.'

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Создайте .venv и установите requirements-build.txt перед сборкой.'
}
& $pythonPath -m PyInstaller --noconfirm --clean --onefile --name DocumentSearch `
    --collect-all elasticsearch --collect-all elastic_transport `
    --hidden-import uvicorn.logging --hidden-import uvicorn.loops.asyncio `
    --hidden-import uvicorn.protocols.http.h11_impl --hidden-import uvicorn.lifespan.on windows_entry.py
if ($LASTEXITCODE -ne 0) { throw 'Сборка EXE завершилась с ошибкой.' }
& (Join-Path $projectRoot 'dist\DocumentSearch.exe') --version
if ($LASTEXITCODE -ne 0) { throw 'EXE не прошёл проверку запуска.' }

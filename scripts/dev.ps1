# Windows equivalent of `make dev`: API on :8000, UI on :5173.
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\pip install -e '.[dev]'
    Push-Location ui; npm install; Pop-Location
}

$api = Start-Process -PassThru -NoNewWindow .\.venv\Scripts\python `
    -ArgumentList "-m", "uvicorn", "bsos.api.app:app", "--reload", "--port", "8000"
Push-Location ui
try {
    npm run dev
} finally {
    Pop-Location
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
}

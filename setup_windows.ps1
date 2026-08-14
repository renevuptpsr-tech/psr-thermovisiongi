$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\app.py")) {
    throw "Jalankan skrip ini dari folder yang berisi app.py."
}

$venvPython = ".\.venv\Scripts\python.exe"

if ((Test-Path ".\.venv") -and -not (Test-Path $venvPython)) {
    $backup = ".venv_incomplete_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Rename-Item ".\.venv" $backup
    Write-Host "Virtual environment yang tidak lengkap dipindahkan ke $backup" -ForegroundColor Yellow
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Membuat virtual environment. Tunggu hingga prompt PowerShell kembali..." -ForegroundColor Cyan
    python -m venv .venv
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path ".\.streamlit\secrets.toml")) {
    Copy-Item ".\.streamlit\secrets.toml.example" ".\.streamlit\secrets.toml"
    Write-Host "secrets.toml dibuat. Isi kredensial sebelum menjalankan aplikasi." -ForegroundColor Yellow
}

Write-Host "Setup selesai." -ForegroundColor Green
Write-Host "Jalankan: .\run_windows.ps1"


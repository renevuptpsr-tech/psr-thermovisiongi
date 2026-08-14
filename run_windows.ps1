$ErrorActionPreference = "Stop"

$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment belum siap. Jalankan .\setup_windows.ps1 terlebih dahulu."
}

if (-not (Test-Path ".\.streamlit\secrets.toml")) {
    throw "File .streamlit\secrets.toml belum tersedia."
}

& $venvPython -m streamlit run app.py


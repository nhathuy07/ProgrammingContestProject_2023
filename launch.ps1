if (-not (Test-Path ".venv/Scripts")) {
    Write-Host "Setting up required packages..."
    python -m venv .venv
    .venv/Scripts/pip3.exe install -r "REQUIREMENTS.txt"
}
else {
    Write-Host "Setup not necessary, skipping..."
}
Start-Process -FilePath ".venv/Scripts/uvicorn.exe" -ArgumentList "server:server --reload"
& .venv/Scripts/Activate.ps1
& .venv/Scripts/python.exe ./client.py
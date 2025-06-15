# Build script for TetraX Host on Windows (PowerShell)
# Usage: .\build_windows.ps1

Write-Host "🔧 Building TetraX Host for Windows..." -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Blue

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ $pythonVersion found" -ForegroundColor Green
} catch {
    Write-Host "❌ Python is required but not installed." -ForegroundColor Red
    Write-Host "Please install Python from https://python.org" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if pip is installed
try {
    $pipVersion = pip --version 2>&1
    Write-Host "✅ pip found" -ForegroundColor Green
} catch {
    Write-Host "❌ pip is required but not installed." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "✅ Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "🚀 Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "⬆️ Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install requirements
Write-Host "📋 Installing requirements..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install requirements" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Install PyInstaller
Write-Host "🔨 Installing PyInstaller..." -ForegroundColor Yellow
pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install PyInstaller" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Clean previous builds
Write-Host "🧹 Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# Build the executable
Write-Host "🏗️ Building executable..." -ForegroundColor Yellow
pyinstaller tetrax_host.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ PyInstaller build failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if build was successful
if (Test-Path "dist\tetrax_host.exe") {
    Write-Host "✅ Build successful!" -ForegroundColor Green
    Write-Host "📁 Executable created at: dist\tetrax_host.exe" -ForegroundColor Cyan
    
    # Show file info
    Write-Host "📊 File information:" -ForegroundColor Yellow
    Get-ChildItem "dist\tetrax_host.exe" | Format-Table Name, Length, LastWriteTime
    
    $size = (Get-Item "dist\tetrax_host.exe").Length / 1MB
    Write-Host "📊 File size: $([math]::Round($size, 1)) MB" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "🎉 You can now run the application with: dist\tetrax_host.exe" -ForegroundColor Green
} else {
    Write-Host "❌ Build failed! Executable not found." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Build completed successfully!" -ForegroundColor Green
Read-Host "Press Enter to exit"

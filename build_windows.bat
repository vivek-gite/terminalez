@echo off
REM Build script for TetraX Host on Windows
REM Usage: build_windows.bat

echo 🔧 Building TetraX Host for Windows...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is required but not installed.
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if pip is installed
pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip is required but not installed.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🚀 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️ Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo 📋 Installing requirements...
pip install -r requirements.txt

REM Install PyInstaller
echo 🔨 Installing PyInstaller...
pip install pyinstaller

REM Clean previous builds
echo 🧹 Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM Build the executable
echo 🏗️ Building executable...
pyinstaller tetrax_host.spec

REM Check if build was successful
if exist "dist\tetrax_host.exe" (
    echo ✅ Build successful!
    echo 📁 Executable created at: dist\tetrax_host.exe
    
    REM Show file info
    echo 📊 File information:
    dir "dist\tetrax_host.exe"
    
    echo.
    echo 🎉 You can now run the application with: dist\tetrax_host.exe
) else (
    echo ❌ Build failed!
    pause
    exit /b 1
)

pause

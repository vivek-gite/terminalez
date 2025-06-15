#!/bin/bash

# Build script for TetraX Host on Unix systems (Linux/macOS)
# Usage: ./build_unix.sh

set -e  # Exit on any error

echo "🔧 Building TetraX Host for Unix systems..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🚀 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📋 Installing requirements..."
pip install -r requirements.txt

# Install PyInstaller
echo "🔨 Installing PyInstaller..."
pip install pyinstaller

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist

# Build the executable
echo "🏗️ Building executable..."
pyinstaller tetrax_host_unix.spec

# Check if build was successful
if [ -f "dist/tetrax_host" ]; then
    echo "✅ Build successful!"
    echo "📁 Executable created at: dist/tetrax_host"
    
    # Make the executable actually executable
    chmod +x dist/tetrax_host
    
    # Show file info
    echo "📊 File information:"
    ls -la dist/tetrax_host
    file dist/tetrax_host
    
    echo ""
    echo "🎉 You can now run the application with: ./dist/tetrax_host"
else
    echo "❌ Build failed!"
    exit 1
fi

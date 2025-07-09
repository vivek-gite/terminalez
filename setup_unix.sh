#!/bin/bash

# TetraX Host - Unix Setup Script
# This script sets up the development environment and builds the application

set -e

echo "🔧 TetraX Host - Unix Setup Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    printf "${1}${2}${NC}\n"
}

# Check if we're on a Unix system
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    print_color $RED "❌ This setup script is for Unix systems (Linux/macOS)."
    print_color $YELLOW "For Windows, use the existing tetrax_host.spec file."
    exit 1
fi

print_color $GREEN "✅ Detected Unix system: $OSTYPE"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    print_color $RED "❌ Python 3 is required but not installed."
    print_color $YELLOW "Please install Python 3:"
    echo ""
    echo "Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "CentOS/RHEL:   sudo yum install python3 python3-pip"
    echo "macOS:         brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
print_color $GREEN "✅ Python $PYTHON_VERSION found"

# Check for pip3
if ! command -v pip3 &> /dev/null; then
    print_color $RED "❌ pip3 is required but not installed."
    exit 1
fi

print_color $GREEN "✅ pip3 found"

# Make scripts executable
print_color $BLUE "🔧 Making scripts executable..."
chmod +x build_unix.py 2>/dev/null || true
chmod +x build_unix.sh 2>/dev/null || true
chmod +x run.sh 2>/dev/null || true

print_color $GREEN "✅ Scripts are now executable"

# Ask user what they want to do
echo ""
print_color $YELLOW "What would you like to do?"
echo "1) Build the application now"
echo "2) Set up development environment only"
echo "3) Show build instructions"
echo "4) Exit"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        print_color $BLUE "🏗️ Building the application..."
        if [ -f "build_unix.py" ]; then
            python3 build_unix.py
        else
            print_color $RED "❌ Build script not found!"
            exit 1
        fi
        
        if [ -f "dist/tetrax_host" ]; then
            print_color $GREEN "🎉 Build completed successfully!"
            echo ""
            print_color $YELLOW "You can now run the application with:"
            echo "  ./dist/tetrax_host"
            echo "  or"
            echo "  ./run.sh"
            echo ""
            print_color $BLUE "ℹ️  Platform Note:"
            echo "  This executable is built for $(uname -s) on $(uname -m)"
            echo "  It will NOT run on other operating systems"
            echo "  For other platforms, build on the target system"
        fi
        ;;
    
    2)
        print_color $BLUE "📦 Setting up development environment..."
        
        # Create virtual environment
        if [ ! -d "venv" ]; then
            python3 -m venv venv
            print_color $GREEN "✅ Virtual environment created"
        else
            print_color $YELLOW "Virtual environment already exists"
        fi
        
        # Activate and install dependencies
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller
        
        print_color $GREEN "✅ Development environment ready!"
        echo ""
        print_color $YELLOW "To activate the environment:"
        echo "  source venv/bin/activate"
        echo ""
        print_color $YELLOW "To build the application:"
        echo "  ./build_unix.py"
        echo "  or"
        echo "  make build"
        ;;
    
    3)
        print_color $BLUE "📖 Build Instructions:"
        echo ""
        echo "Method 1 - Python script (recommended):"
        echo "  ./build_unix.py"
        echo ""
        echo "Method 2 - Shell script:"
        echo "  ./build_unix.sh"
        echo ""
        echo "Method 3 - Make:"
        echo "  make build"
        echo ""
        echo "Method 4 - Manual:"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt pyinstaller"
        echo "  pyinstaller tetrax_host_unix.spec"
        echo ""
        print_color $YELLOW "For detailed instructions, see BUILD_UNIX.md"
        ;;
    
    4)
        print_color $BLUE "👋 Goodbye!"
        exit 0
        ;;
    
    *)
        print_color $RED "❌ Invalid choice"
        exit 1
        ;;
esac

print_color $GREEN "✅ Setup completed!"

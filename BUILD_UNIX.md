# TetraX Host - Unix Build Instructions

This guide explains how to build the TetraX Host application for Unix-based systems (Linux and macOS).

## Prerequisites

- Python 3.7 or higher
- pip3
- Git (optional, for cloning)

### System-specific requirements:

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv

# CentOS/RHEL/Fedora
sudo yum install python3 python3-pip
# or
sudo dnf install python3 python3-pip
```

**macOS:**
```bash
# Using Homebrew
brew install python3

# Or download from python.org
# Python 3 usually comes with macOS, but you might need to install pip
```

## Build Methods

You have several options to build the application:

### Method 1: Using Python Build Script (Recommended)

```bash
# Make the script executable
chmod +x build_unix.py

# Run the build script
./build_unix.py
```

Or run directly with Python:
```bash
python3 build_unix.py
```

### Method 2: Using Shell Script

```bash
# Make the script executable
chmod +x build_unix.sh

# Run the build script
./build_unix.sh
```

### Method 3: Using Makefile

```bash
# Build the application
make build

# Or just run make (build is the default target)
make
```

Other make targets:
```bash
make install    # Install dependencies only
make dev        # Run in development mode
make run        # Run the built executable
make test       # Test the build
make clean      # Clean build artifacts
make clean-all  # Clean everything including virtual environment
make help       # Show available targets
```

### Method 4: Manual Build

If you prefer to build manually:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Clean previous builds
rm -rf build dist

# Build the executable
pyinstaller tetrax_host_unix.spec

# Make executable
chmod +x dist/tetrax_host
```

## Running the Application

After a successful build, you can run the application:

```bash
./dist/tetrax_host
```

## Build Output

The build process will create:
- `dist/tetrax_host` - The main executable
- `build/` - Temporary build files (can be deleted)
- `venv/` - Virtual environment (used by build scripts)

## Troubleshooting

### Common Issues:

1. **Permission denied when running executable**
   ```bash
   chmod +x dist/tetrax_host
   ```

2. **Missing Python modules**
   - Make sure all dependencies are installed
   - Try rebuilding with a clean virtual environment

3. **Build fails on missing system libraries**
   - Install development tools for your system:
   
   **Linux:**
   ```bash
   # Ubuntu/Debian
   sudo apt install build-essential
   
   # CentOS/RHEL
   sudo yum groupinstall "Development Tools"
   ```
   
   **macOS:**
   ```bash
   xcode-select --install
   ```

4. **PyInstaller not found**
   - Make sure PyInstaller is installed in your virtual environment
   - Activate the virtual environment before building

### Getting Help

If you encounter issues:
1. Check that all prerequisites are installed
2. Try cleaning and rebuilding: `make clean-all && make build`
3. Check the build logs for specific error messages
4. Ensure you're using a supported Python version (3.7+)

## Development Mode

To run the application in development mode without building:

```bash
# Using make
make dev

# Or manually
python3 core/host_core/main.py
```

## Cross-Platform Notes

- This Unix build configuration excludes Windows-specific modules
- The application uses `UnixPTyTerminal` for terminal handling on Unix systems
- The build includes Unix-specific modules like `pty`, `termios`, `fcntl`, etc.

## File Structure

The Unix build uses these key files:
- `tetrax_host_unix.spec` - PyInstaller specification for Unix
- `build_unix.py` - Python build script
- `build_unix.sh` - Shell build script  
- `Makefile` - Make-based build system
- `requirements.txt` - Python dependencies

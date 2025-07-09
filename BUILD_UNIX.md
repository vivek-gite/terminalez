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

## Cross-Platform Notes and Binary Compatibility

### ⚠️ Important: Platform-Specific Executables

**Executables built on one platform CANNOT run on another platform:**

- **Linux executable** (.bin or no extension): Only runs on Linux
- **macOS executable**: Only runs on macOS  
- **Windows executable** (.exe): Only runs on Windows

This is because:
- Different executable formats (ELF vs Mach-O vs PE)
- Different system APIs and libraries
- Different CPU architectures may be involved

### Building for Multiple Platforms

To distribute your application for multiple platforms:

1. **Build on Linux** (for Linux users):
   ```bash
   ./build_unix.py  # Creates: dist/tetrax_host-linux-x86_64
   ```

2. **Build on macOS** (for macOS users):
   ```bash
   ./build_unix.py  # Creates: dist/tetrax_host-macos-arm64 (or x86_64)
   ```

3. **Build on Windows** (for Windows users):
   ```bash
   # Use the Windows-specific build process
   ```

### Platform Detection

The build script automatically:
- Detects your platform and architecture
- Creates platform-specific executable names
- Shows compatibility warnings
- Uses Unix-specific modules (pty, termios, fcntl) for Unix systems

### Running .bin Files

If you have a `.bin` file that works on Linux but not macOS:
- This is expected behavior - they are incompatible
- You must build separately on each target platform
- Consider using containerization (Docker) for consistent deployment

## Alternative Cross-Platform Build Solutions

Since you may not have access to all target platforms, here are alternative approaches:

### 1. GitHub Actions (Recommended)

Use the included GitHub Actions workflow (`.github/workflows/build-cross-platform.yml`) to automatically build for multiple platforms:

1. **Push your code to GitHub**
2. **GitHub Actions will automatically build for:**
   - Linux (x86_64)
   - macOS (both Intel and Apple Silicon)
   - Windows (when configured)

3. **Download the built executables** from the Actions artifacts

**Setup:**
```bash
# Commit and push the workflow file
git add .github/workflows/build-cross-platform.yml
git commit -m "Add cross-platform build workflow"
git push
```

### 2. Docker-Based Builds

Use Docker to create consistent build environments:

```bash
# Build using Docker (Linux containers only)
./build_docker.sh

# Or manually with Docker
docker build -f Dockerfile.multiplatform .
```

**Limitations:** Docker builds create Linux executables only, not true macOS binaries.

### 3. Cloud Build Services

Alternative cloud services for cross-platform builds:

- **GitHub Actions** (free for public repos)
- **GitLab CI/CD** (includes macOS runners)
- **Azure DevOps** (cross-platform builds)
- **Travis CI** (supports macOS)

### 4. Virtual Machines

If you need occasional macOS builds:

- **macOS VM** (requires Apple hardware legally)
- **Cloud macOS instances** (MacStadium, AWS EC2 Mac)
- **GitHub Codespaces** with macOS runners

### 5. Cross-Compilation (Experimental)

Limited support, may not work reliably:

```bash
# Attempt cross-compilation (experimental)
python build_unix.py --cross-compile
```

**Note:** This rarely works for Python applications with native dependencies.

## File Structure

The Unix build uses these key files:
- `tetrax_host_unix.spec` - PyInstaller specification for Unix
- `build_unix.py` - Python build script
- `build_unix.sh` - Shell build script  
- `Makefile` - Make-based build system
- `requirements.txt` - Python dependencies

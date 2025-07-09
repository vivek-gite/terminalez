#!/usr/bin/env python3
"""
Build script for TetraX Host on Unix systems (Linux/macOS)
This script automates the build process using PyInstaller.
"""

import os
import sys
import subprocess
import shutil
import venv
from pathlib import Path
import platform

def run_command(cmd, description, check=True):
    """Run a command with error handling."""
    print(f"🔧 {description}...")
    try:
        if isinstance(cmd, str):
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        
        if result.stdout:
            print(result.stdout)
        if result.stderr and result.returncode != 0:
            print(f"Warning: {result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}:")
        print(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        print(f"Return code: {e.returncode}")
        if e.stdout:
            print(f"Stdout: {e.stdout}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        sys.exit(1)

def check_system():
    """Check if we're on a Unix system."""
    if os.name == 'nt':
        print("❌ This build script is for Unix systems (Linux/macOS).")
        print("For Windows, use the existing tetrax_host.spec file.")
        sys.exit(1)
    
    print(f"✅ Detected system: {sys.platform}")

def setup_venv():
    """Set up virtual environment."""
    venv_dir = Path("venv")
    
    if not venv_dir.exists():
        print("📦 Creating virtual environment...")
        venv.create("venv", with_pip=True)
    else:
        print("✅ Virtual environment already exists")
    
    return venv_dir

def get_venv_python(venv_dir):
    """Get the path to the Python executable in the virtual environment."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    else:
        return venv_dir / "bin" / "python"

def install_dependencies(venv_python):
    """Install required dependencies."""
    # Upgrade pip
    run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], 
                "Upgrading pip")
    
    # Install requirements
    run_command([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"], 
                "Installing requirements")
    
    # Install PyInstaller
    run_command([str(venv_python), "-m", "pip", "install", "pyinstaller"], 
                "Installing PyInstaller")

def clean_build():
    """Clean previous build artifacts."""
    print("🧹 Cleaning previous builds...")
    
    dirs_to_clean = ["build", "dist"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed {dir_name}/")

def build_executable(venv_python):
    """Build the executable using PyInstaller."""
    spec_file = "tetrax_host_unix.spec"
    
    if not os.path.exists(spec_file):
        print(f"❌ Spec file {spec_file} not found!")
        sys.exit(1)
    
    run_command([str(venv_python), "-m", "PyInstaller", spec_file], 
                "Building executable with PyInstaller")

def get_platform_name():
    """Get platform-specific name for the executable."""
    import platform
    
    if sys.platform.startswith('linux'):
        arch = platform.machine()
        return f"linux-{arch}"
    elif sys.platform == 'darwin':
        arch = platform.machine()
        return f"macos-{arch}"
    else:
        return "unix"

def verify_build():
    """Verify the build was successful."""
    original_executable = Path("dist/tetrax_host")
    platform_name = get_platform_name()
    platform_executable = Path(f"dist/tetrax_host-{platform_name}")
    
    if original_executable.exists():
        print("✅ Build successful!")
        
        # Make executable
        os.chmod(original_executable, 0o755)
        
        # Create platform-specific copy
        shutil.copy2(original_executable, platform_executable)
        os.chmod(platform_executable, 0o755)
        
        # Show file info
        print(f"📁 Executable created at: {original_executable}")
        print(f"📁 Platform-specific copy: {platform_executable}")
        
        # Get file size
        size = original_executable.stat().st_size
        size_mb = size / (1024 * 1024)
        print(f"📊 File size: {size_mb:.1f} MB")
        
        # Test if it's executable
        result = run_command(["file", str(original_executable)], "Checking file type", check=False)
        
        print(f"\n🎉 You can now run the application with:")
        print(f"  ./{original_executable}")
        print(f"  or")
        print(f"  ./{platform_executable}")
        
        # Show platform compatibility warning
        print(f"\n⚠️  Platform Compatibility:")
        if sys.platform.startswith('linux'):
            print("  This executable will only run on Linux systems")
        elif sys.platform == 'darwin':
            print("  This executable will only run on macOS systems")
        print("  To run on other platforms, build on that target platform")
        
        return True
    else:
        print("❌ Build failed! Executable not found.")
        return False

def build_cross_platform():
    """Attempt cross-platform builds (experimental)."""
    print("🌐 Attempting cross-platform builds...")
    print("⚠️  Note: Cross-compilation has limitations and may not work reliably")
    
    # This is experimental and may not work
    platforms = ['linux', 'darwin']  # 'win32' would need different handling
    current_platform = sys.platform
    
    for target_platform in platforms:
        if target_platform == current_platform:
            continue
            
        print(f"\n🔄 Attempting to build for {target_platform}...")
        try:
            # This is highly experimental and likely to fail
            env = os.environ.copy()
            env['PYINSTALLER_TARGET_PLATFORM'] = target_platform
            
            spec_file = "tetrax_host_unix.spec"
            venv_python = get_venv_python(Path("venv"))
            
            result = run_command([
                str(venv_python), "-m", "PyInstaller", 
                "--target-platform", target_platform,
                spec_file
            ], f"Cross-compiling for {target_platform}", check=False)
            
            if result.returncode == 0:
                print(f"✅ Cross-compilation for {target_platform} succeeded (experimental)")
            else:
                print(f"❌ Cross-compilation for {target_platform} failed (expected)")
                
        except Exception as e:
            print(f"❌ Cross-compilation failed: {e}")

def build_with_docker():
    """Build using Docker for cross-platform support."""
    print("🐳 Building with Docker for cross-platform support...")
    
    # Check if Docker is available
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Docker not found. Please install Docker for cross-platform builds.")
        return False
    
    # Create Dockerfile for cross-platform builds
    dockerfile_content = '''
# Multi-stage build for cross-platform Python applications
FROM python:3.9-slim as base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyinstaller

# Copy source code
COPY . .

# Build the application
RUN python build_unix.py

# Create output stage
FROM scratch as output
COPY --from=base /app/dist/ /dist/
'''
    
    with open("Dockerfile.cross", "w") as f:
        f.write(dockerfile_content)
    
    print("📝 Created Dockerfile.cross for cross-platform builds")
    print("🔧 To build for different platforms, use:")
    print("   docker buildx build --platform linux/amd64,linux/arm64 .")
    
    return True

def main():
    """Main build function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build TetraX Host for Unix systems')
    parser.add_argument('--cross-compile', action='store_true', 
                       help='Attempt experimental cross-compilation')
    parser.add_argument('--docker', action='store_true',
                       help='Setup Docker-based build')
    args = parser.parse_args()
    
    print("🔧 Building TetraX Host for Unix systems...")
    print("=" * 50)
    
    if args.docker:
        return build_with_docker()
    
    # Check system compatibility
    check_system()
    
    # Set up virtual environment
    venv_dir = setup_venv()
    venv_python = get_venv_python(venv_dir)
    
    # Install dependencies
    install_dependencies(venv_python)
    
    # Clean previous builds
    clean_build()
    
    # Build executable
    build_executable(venv_python)
    
    # Attempt cross-compilation if requested
    if args.cross_compile:
        build_cross_platform()
    
    # Verify build
    if verify_build():
        print("\n" + "=" * 50)
        print("🎉 Build completed successfully!")
        
        if args.cross_compile:
            print("\n⚠️  Cross-compilation is experimental and may not work")
            print("   For reliable macOS builds, use GitHub Actions or build on macOS")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

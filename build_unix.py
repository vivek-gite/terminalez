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

def verify_build():
    """Verify the build was successful."""
    executable_path = Path("dist/tetrax_host")
    
    if executable_path.exists():
        print("✅ Build successful!")
        
        # Make executable
        os.chmod(executable_path, 0o755)
        
        # Show file info
        print(f"📁 Executable created at: {executable_path}")
        
        # Get file size
        size = executable_path.stat().st_size
        size_mb = size / (1024 * 1024)
        print(f"📊 File size: {size_mb:.1f} MB")
        
        # Test if it's executable
        result = run_command(["file", str(executable_path)], "Checking file type", check=False)
        
        print(f"\n🎉 You can now run the application with: ./{executable_path}")
        return True
    else:
        print("❌ Build failed! Executable not found.")
        return False

def main():
    """Main build function."""
    print("🔧 Building TetraX Host for Unix systems...")
    print("=" * 50)
    
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
    
    # Verify build
    if verify_build():
        print("\n" + "=" * 50)
        print("🎉 Build completed successfully!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

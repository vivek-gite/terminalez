#!/bin/bash

# Simple launcher script for TetraX Host
# This script will automatically detect if the executable exists and run it,
# or offer to build it if it doesn't exist.

EXECUTABLE="dist/tetrax_host"

if [ -f "$EXECUTABLE" ]; then
    echo "🚀 Starting TetraX Host..."
    ./"$EXECUTABLE"
else
    echo "❌ TetraX Host executable not found at $EXECUTABLE"
    echo ""
    echo "Would you like to build it now? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "🔧 Building TetraX Host..."
        
        # Try different build methods
        if [ -f "build_unix.py" ]; then
            python3 build_unix.py
        elif [ -f "Makefile" ]; then
            make build
        elif [ -f "build_unix.sh" ]; then
            chmod +x build_unix.sh
            ./build_unix.sh
        else
            echo "❌ No build scripts found!"
            exit 1
        fi
        
        # Try to run after building
        if [ -f "$EXECUTABLE" ]; then
            echo "🚀 Starting TetraX Host..."
            ./"$EXECUTABLE"
        else
            echo "❌ Build failed or executable not created"
            exit 1
        fi
    else
        echo "Please build TetraX Host first using one of these methods:"
        echo "  - ./build_unix.py"
        echo "  - make build"
        echo "  - ./build_unix.sh"
        exit 1
    fi
fi

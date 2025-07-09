#!/bin/bash

# Cross-platform build script using Docker
# This script builds the application for multiple platforms using Docker

set -e

echo "🐳 TetraX Host - Cross-Platform Docker Build"
echo "============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_color() {
    printf "${1}${2}${NC}\n"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_color $RED "❌ Docker is not installed!"
    echo ""
    echo "Please install Docker first:"
    echo "  Linux: https://docs.docker.com/engine/install/"
    echo "  macOS: https://docs.docker.com/desktop/mac/"
    echo "  Windows: https://docs.docker.com/desktop/windows/"
    exit 1
fi

print_color $GREEN "✅ Docker found"

# Check if buildx is available for multi-platform builds
if docker buildx version &> /dev/null; then
    print_color $GREEN "✅ Docker Buildx available for multi-platform builds"
    BUILDX_AVAILABLE=true
else
    print_color $YELLOW "⚠️  Docker Buildx not available - single platform builds only"
    BUILDX_AVAILABLE=false
fi

# Create output directory
mkdir -p dist-docker

echo ""
print_color $YELLOW "Select build option:"
echo "1) Build for current platform only"
echo "2) Build for multiple platforms (requires Docker Buildx)"
echo "3) Build and extract executables"
echo "4) Show available platforms"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        print_color $BLUE "🔨 Building for current platform..."
        docker build -f Dockerfile.multiplatform -t tetrax-host:latest .
        
        # Extract the executable
        print_color $BLUE "📦 Extracting executable..."
        docker run --rm -v "$(pwd)/dist-docker:/output" tetrax-host:latest sh -c "cp -r dist/* /output/"
        
        print_color $GREEN "✅ Build completed! Check dist-docker/ folder"
        ;;
    
    2)
        if [ "$BUILDX_AVAILABLE" = false ]; then
            print_color $RED "❌ Docker Buildx is required for multi-platform builds"
            exit 1
        fi
        
        print_color $BLUE "🌐 Building for multiple platforms..."
        
        # Create a new builder instance
        docker buildx create --name multiplatform-builder --use --bootstrap 2>/dev/null || true
        
        # Build for multiple platforms
        docker buildx build \
            --platform linux/amd64,linux/arm64 \
            -f Dockerfile.multiplatform \
            --target export \
            --output type=local,dest=./dist-docker \
            .
        
        print_color $GREEN "✅ Multi-platform build completed! Check dist-docker/ folder"
        ;;
    
    3)
        print_color $BLUE "🔨 Building and extracting executables..."
        
        # Build the image
        docker build -f Dockerfile.multiplatform --target export -t tetrax-export .
        
        # Create a temporary container and copy files
        CONTAINER_ID=$(docker create tetrax-export)
        docker cp "$CONTAINER_ID:/" ./dist-docker/
        docker rm "$CONTAINER_ID"
        
        print_color $GREEN "✅ Executables extracted to dist-docker/ folder"
        ;;
    
    4)
        print_color $BLUE "📋 Available platforms for Docker builds:"
        echo ""
        if [ "$BUILDX_AVAILABLE" = true ]; then
            docker buildx ls
            echo ""
            print_color $YELLOW "Common platforms:"
            echo "  linux/amd64   - Linux x86_64"
            echo "  linux/arm64   - Linux ARM64"
            echo "  linux/arm/v7  - Linux ARM v7"
        else
            print_color $YELLOW "Current platform only (install Docker Buildx for more options)"
        fi
        ;;
    
    *)
        print_color $RED "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
print_color $BLUE "📋 Build Summary:"
if [ -d "dist-docker" ]; then
    echo "Built files:"
    find dist-docker -type f -name "tetrax_host*" -exec ls -la {} \;
    
    echo ""
    print_color $YELLOW "Note: These executables are built in a Linux container"
    print_color $YELLOW "They will work on Linux systems with compatible architecture"
    print_color $YELLOW "For true macOS executables, you still need to build on macOS"
fi

echo ""
print_color $GREEN "🐳 Docker build process completed!"

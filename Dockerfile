# Use Python 3.12 official Debian slim image for better package compatibility
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for compiling Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Expose ports
EXPOSE 8000 50051

# Start the server
CMD ["python", "-m", "core.server_core.main"]

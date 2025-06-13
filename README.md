# Tetrax Terminal Management System

## Overview

Tetrax is a distributed terminal management system that allows for seamless terminal session management across different machines. It uses a client-server architecture with gRPC for communication and supports multiple terminal types on Windows.

## Core Components

### Host Core

- **ConsoleHandler**: Manages multiple terminal sessions and their I/O operations
- **ConPTyRunner**: Interfaces with Windows console API to create and manage terminal processes
- **ConPTyTerminal**: Handles terminal I/O operations using the ConPTY API
- **Controller**: Manages gRPC communication with the server

### Comms Core

- **Proto**: Contains Protocol Buffer definitions for gRPC communication
- **Utils**: Utility functions for communication and process management

### Server Core

- **Server Handle**: gRPC server implementation
- **State Manager**: Manages terminal session state
- **Web**: Web interface for terminal sessions

## Getting Started

### Prerequisites

- Windows 10/11
- Python 3.9+
- gRPC libraries

### Installation

1. Clone the repository:
   ```powershell
   git clone https://github.com/tetrax/tetrax.git
   cd tetrax
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Generate Protocol Buffer code:
   ```powershell
   python core/comms_core/proto/run_codegen.py
   ```

### Running the System

1. Start the server:
   ```powershell
   python -m core.server_core.main
   ```

2. Start the client:
   ```powershell
   python -m core.host_core.main
   ```

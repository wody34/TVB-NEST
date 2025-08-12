# Nix Installation and Development Environment

This directory contains Nix-specific installation guides and configuration for the TVB-NEST development environment.

## Files

- `../../flake.nix` - Main Nix flake configuration
- `../../flake.lock` - Lock file with pinned dependencies  
- `test_module_imports.py` - Python module import testing script
- `README.md` - This installation guide

## Installation

### Prerequisites
1. **Install Nix** (if not already installed):
   ```bash
   # Multi-user installation (recommended)
   sh <(curl -L https://nixos.org/nix/install) --daemon
   
   # Enable flakes (required)
   echo "experimental-features = nix-command flakes" | sudo tee -a /etc/nix/nix.conf
   ```

2. **Enable Nix flakes** (if not enabled):
   ```bash
   # Add to ~/.config/nix/nix.conf or /etc/nix/nix.conf
   experimental-features = nix-command flakes
   ```

## Usage

### Development Environment
```bash
# Default environment (no Jupyter)
nix develop

# With Jupyter Lab support
nix develop .#with-jupyter
```

### Key Features
- NEST Simulator with MPI support
- UV + Nix hybrid package management
- Automatic mpi4py compatibility handling
- Cross-platform support (macOS/Linux)

### Environment Setup Flow
1. `setupEnvironment` - Environment variables
2. `initializeUVProject` - UV project initialization  
3. `installPythonPackages` - Package installation
4. `activateEnvironment` - Virtual environment activation
5. `fixMPI4PyCompatibility` - MPI library compatibility
6. `testModuleImports` - Import verification
7. `showWelcome` - Ready status

## Configuration Validation

The flake includes build-time validation for:
- Jupyter port numbers (1024-65535)
- GitHub repository URLs
- Git commit SHA format

## Troubleshooting

### Common Issues
- **mpi4py conflicts**: Automatically resolved by symlink to Nix's version
- **Package installation failures**: Non-critical packages fail gracefully
- **Import errors**: Detailed error reporting with module-specific diagnostics

### Development
The environment supports both interactive development and automated testing workflows.
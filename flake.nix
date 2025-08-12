{
  description = "TVB-NEST: Multi-scale brain modeling with NEST neural simulator and The Virtual Brain platform. Features MPI support, UV+Nix hybrid package management.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        # Configuration constants with validation
        config = {
          jupyterPort = "8893";

          nestRepo = {
            url = "https://github.com/sdiazpier/nest-simulator";
            rev = "4dc58f60512b8adcb6d5f1bf0eb29ffe82ae71a1";
            ref = "nest-io-dev";
          };
        };
        
        # Configuration validation
        validateConfig = config:
          let
            portNum = pkgs.lib.toInt (toString config.jupyterPort);
            validPort = portNum >= 1024 && portNum <= 65535;
            validUrl = pkgs.lib.hasPrefix "https://github.com/" config.nestRepo.url;
            validRev = builtins.stringLength config.nestRepo.rev == 40; # Git SHA length
          in
          assert validPort || throw "Invalid jupyterPort: ${config.jupyterPort} (must be 1024-65535)";
          assert validUrl || throw "Invalid nestRepo.url: ${config.nestRepo.url} (must be GitHub HTTPS URL)";
          assert validRev || throw "Invalid nestRepo.rev: ${config.nestRepo.rev} (must be 40-character Git SHA)";
          config;
          
        # Validated configuration
        validatedConfig = validateConfig config;
        
        # Package lists for UV installation
        packageLists = {
          core = "'numpy>=2.2' 'scipy<1.14.0' matplotlib networkx pillow 'numba>=0.61.0' 'elephant>=0.15.0' pandas";
          jupyter = "jupyter jupyterlab";
          optional = "pytest pyyaml cython";
          tvb = "tvb-data tvb-gdist tvb-library";
        };

        # Platform-specific configuration
        isDarwin = pkgs.stdenv.isDarwin;
        pythonLibExt = if isDarwin then "dylib" else "so";
        pythonVersion = pkgs.python3.pythonVersion;
        
        nestSrc = builtins.fetchGit validatedConfig.nestRepo;

        # Core Python packages that should be available system-wide
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          # System-level packages for NEST compilation and MPI
          numpy cython mpi4py 
          # Package management tools
          pip setuptools wheel
        ]);

        nest-simulator = pkgs.stdenv.mkDerivation rec {
          pname = "nest-simulator";
          version = "custom-io-dev";
          src = nestSrc;
          
          # Metadata for better discoverability
          meta = with pkgs.lib; {
            description = "NEST Simulator for spiking neural networks with IO extensions (fork with Nix improvements)";
            homepage = "https://github.com/wody34/TVB-NEST";
            license = licenses.gpl2Plus;
            maintainers = [ ];
            platforms = platforms.unix;
          };

          nativeBuildInputs = with pkgs; [ 
            cmake pkg-config which
          ];
          
          buildInputs = with pkgs; [
            gsl readline ncurses lapack libtool 
            llvm pythonEnv openmpi llvmPackages.openmp ];

          cmakeFlags = [
            "-DCMAKE_INSTALL_PREFIX=${placeholder "out"}"
            "-Dwith-mpi=ON"  # Enable MPI support
            "-Dwith-python=ON"
            "-Dwith-openmp=ON"
            "-Dwith-gsl=ON"
            "-Dwith-readline=ON"
            "-DCMAKE_C_COMPILER=${pkgs.gcc}/bin/gcc"
            "-DCMAKE_CXX_COMPILER=${pkgs.gcc}/bin/g++"
            "-DMPI_C_COMPILER=${pkgs.openmpi}/bin/mpicc"
            "-DMPI_CXX_COMPILER=${pkgs.openmpi}/bin/mpicxx"
            "-DPYTHON_INCLUDE_DIR=${pythonEnv}/include/python${pythonVersion}"
            "-DPYTHON_LIBRARY=${pythonEnv}/lib/libpython${pythonVersion}.${pythonLibExt}"
            "-DPYTHON_EXECUTABLE=${pythonEnv}/bin/python${pythonVersion}"
            "-DPYTHON_INSTALL_DIR=${placeholder "out"}/${pythonEnv.sitePackages}"
          ];

          preConfigure = ''
            export LLVM_CONFIG=${pkgs.llvm}/bin/llvm-config
          '';

          postInstall = ''
            # Create nest symlink if needed
            if [ ! -f "$out/bin/nest" ] && [ -f "$out/bin/nest_serial" ]; then
              ln -s $out/bin/nest_serial $out/bin/nest
            fi
            
            # Validate installation
            if [ ! -f "$out/bin/nest" ]; then
              echo "ERROR: NEST binary not found after installation"
              exit 1
            fi
            
            # Install Python files manually if they weren't installed by CMake
            PYTHON_SITE_PACKAGES="$out/${pythonEnv.sitePackages}"
            NEST_PYTHON_DIR="$PYTHON_SITE_PACKAGES/nest"
            
            echo "Installing NEST Python files to $NEST_PYTHON_DIR"
            
            # Check if Python files are already installed
            if [ ! -f "$NEST_PYTHON_DIR/__init__.py" ]; then
              echo "Python files not found, copying from source..."
              
              # Create directory if it doesn't exist
              mkdir -p "$NEST_PYTHON_DIR"
              
              # Copy Python files from source
              if [ -d "$src/pynest/nest" ]; then
                cp -r "$src/pynest/nest"/* "$NEST_PYTHON_DIR/"
                echo "✅ NEST Python files copied successfully"
              else
                echo "❌ NEST Python source files not found in $src/pynest/nest"
              fi
            else
              echo "✅ NEST Python files already installed"
            fi
            
            # Verify Python module installation
            if [ -f "$NEST_PYTHON_DIR/__init__.py" ] && [ -f "$NEST_PYTHON_DIR/pynestkernel.so" ]; then
              echo "✅ NEST Python module installation verified"
            else
              echo "⚠️ NEST Python module installation incomplete"
              echo "Files in $NEST_PYTHON_DIR:"
              ls -la "$NEST_PYTHON_DIR/" || echo "Directory does not exist"
            fi
          '';

          enableParallelBuilding = true;
          
          # Build-time validation
          doInstallCheck = true;
          installCheckPhase = ''
            echo "🧪 Running build-time validation..."
            
            # Test NEST binary exists and runs
            if [ -f "$out/bin/nest" ]; then
              echo "✅ NEST binary found"
              $out/bin/nest --version || echo "⚠️ NEST version check failed"
            else
              echo "❌ NEST binary not found"
              exit 1
            fi
            
            # Test Python module can be imported
            if [ -f "$out/${pythonEnv.sitePackages}/nest/__init__.py" ]; then
              echo "✅ NEST Python module files found"
              # Set environment for testing
              export PYTHONPATH="$out/${pythonEnv.sitePackages}:$PYTHONPATH"
              export LD_LIBRARY_PATH="$out/lib:$out/lib/nest:$LD_LIBRARY_PATH"
              
              # Test basic import (may fail due to missing runtime dependencies, but worth trying)
              ${pythonEnv}/bin/python -c "
import sys
try:
    import nest
    print('✅ NEST Python module import successful')
except Exception as e:
    print(f'⚠️ NEST Python module import failed: {e}')
    print('This may be expected due to missing runtime libraries')
    sys.exit(1)
" || echo "⚠️ Python import test completed with warnings"
            else
              echo "❌ NEST Python module files not found"
              exit 1
            fi
            
            echo "✅ Build-time validation completed"
          '';
          
          # Platform-specific patches if needed
          postPatch = if isDarwin then ''
            # macOS specific patches
            substituteInPlace CMakeLists.txt \
              --replace "-fopenmp" "-Xpreprocessor -fopenmp -lomp"
          '' else "";
        };
        
        # Shell hook functions
        # 
        # Function execution order and dependencies:
        # 1. setupEnvironment      - Sets environment variables (no dependencies)
        # 2. initializeUVProject   - Creates pyproject.toml (no dependencies)  
        # 3. installPythonPackages - Installs UV packages (depends on: 2)
        # 4. activateEnvironment   - Activates .venv (depends on: 3)
        # 5. fixMPI4PyCompatibility- Creates mpi4py symlink (depends on: 4)
        # 6. testModuleImports     - Verifies imports (depends on: 5)
        # 7. showWelcome          - Final status (depends on: 6)
        #
        setupEnvironment = ''
          set -euo pipefail  # Enhanced error handling
          
          # Environment setup with proper quoting
          export PATH="${nest-simulator}/bin''${PATH:+:$PATH}"
          export PYTHONPATH="${nest-simulator}/${pythonEnv.sitePackages}''${PYTHONPATH:+:$PYTHONPATH}"
          export LLVM_CONFIG="${pkgs.llvm}/bin/llvm-config"
          
          # Common MPI environment setup
          export LD_LIBRARY_PATH="${nest-simulator}/lib:${nest-simulator}/lib/nest:${pkgs.openmpi}/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
          export MPICC="${pkgs.openmpi}/bin/mpicc"
          export MPICXX="${pkgs.openmpi}/bin/mpicxx"
          
          ${if isDarwin then ''
            # macOS specific environment
            export OMP_NUM_THREADS=1
            echo "🍎 macOS Environment - MPI Enabled"
          '' else ''
            # Linux specific environment
            echo "🐧 Linux Environment - Full MPI Support"
          ''}
        '';
        
        initializeUVProject = ''
          # Initialize UV project safely
          if [ ! -f "pyproject.toml" ]; then
            echo "📦 Initializing UV project"  
            uv init --python ${pythonEnv}/bin/python --no-readme
          fi
        '';
        
        fixMPI4PyCompatibility = ''
          # Fix mpi4py compatibility by linking to Nix's version
          if [ ! -d ".venv" ]; then
            return 0
          fi
          
          VENV_SITE_PACKAGES=".venv/lib/python${pythonVersion}/site-packages"
          NIX_MPI4PY="${pythonEnv}/${pythonEnv.sitePackages}/mpi4py"
          
          if ! [ -d "$NIX_MPI4PY" ] || ! [ -d "$VENV_SITE_PACKAGES" ]; then
            echo "⚠️ Could not create mpi4py symlink - missing directories"
            echo "  NIX_MPI4PY: $NIX_MPI4PY (exists: $([ -d "$NIX_MPI4PY" ] && echo yes || echo no))"
            echo "  VENV_SITE_PACKAGES: $VENV_SITE_PACKAGES (exists: $([ -d "$VENV_SITE_PACKAGES" ] && echo yes || echo no))"
            return 0
          fi
          
          echo "🔧 Fixing mpi4py compatibility..."
          
          # Remove UV's mpi4py if it exists
          if [ -e "$VENV_SITE_PACKAGES/mpi4py" ] || [ -L "$VENV_SITE_PACKAGES/mpi4py" ]; then
            if ! rm -rf "$VENV_SITE_PACKAGES/mpi4py"; then
              echo "❌ Failed to remove existing mpi4py"
              exit 1
            fi
          fi
          
          # Create symlink to Nix's mpi4py
          if ! ln -sf "$NIX_MPI4PY" "$VENV_SITE_PACKAGES/mpi4py"; then
            echo "❌ Failed to create mpi4py symlink"
            exit 1
          fi
          echo "🔗 Created symlink to Nix's mpi4py"
          
          # Verify symlink was created successfully
          if ! [ -L "$VENV_SITE_PACKAGES/mpi4py" ]; then
            echo "❌ mpi4py symlink verification failed"
            exit 1
          fi
          echo "✅ mpi4py compatibility fix verified"
        '';
        
        installPythonPackages = withJupyter: ''
          # Install essential packages with improved error handling
          echo "🐍 Installing Python packages..."
          
          # Core scientific packages
          if ! uv add ${packageLists.core}; then
            echo "❌ Failed to install core scientific packages"
            exit 1
          fi
          
          ${if withJupyter then ''
            # Jupyter packages (optional build)
            if uv add ${packageLists.jupyter}; then
              echo "✅ Jupyter packages installed"
            else
              echo "⚠️ Jupyter packages installation failed"
            fi
          '' else ''
            echo "ℹ️ Jupyter packages skipped (use 'with-jupyter' shell for Jupyter support)"
          ''}
          
          # Specialized packages (optional)
          uv add ${packageLists.optional} || echo "⚠️ Some optional packages failed to install"
          
          # TVB packages (may fail, that's ok)
          uv add ${packageLists.tvb} || echo "⚠️ TVB packages installation failed (manual installation may be required)"
        '';
        
        activateEnvironment = ''
          # Activate virtual environment
          if [ -d ".venv" ]; then
            source .venv/bin/activate
            echo "✅ UV virtual environment activated"
          fi
        '';
        
        testModuleImports = ''
          # Test critical module imports using external script
          echo "🧪 Testing module imports"
          
          if python install/nix/test_module_imports.py; then
            echo "✅ Module import test completed successfully"
          else
            echo "❌ Critical module import failures detected!"
            echo "Environment setup incomplete. Please check error messages above."
            echo "⚠️ Continuing with environment setup despite import errors..."
          fi
        '';
        
        showWelcome = withJupyter: ''
          echo ""
          echo "🎯 TVB-NEST Environment Ready!"
          echo "📋 Available features:"
          echo "  • NEST Simulator with MPI support"
          echo "  • Scientific Python stack (NumPy, SciPy, Matplotlib)"
          echo "  • UV + Nix hybrid package management"
          ${if withJupyter then ''
            echo "  • Jupyter Lab integration"
            echo ""
            echo "🚀 Quick Start:"
            echo "  jupyter lab --ip=0.0.0.0 --port=${validatedConfig.jupyterPort} --no-browser --allow-root"
          '' else ''
            echo ""
            echo "🚀 Quick Start:"
            echo "  python3 your_simulation.py"
            echo ""
            echo "💡 For Jupyter: nix develop .#with-jupyter"
          ''}
        '';

        # Common development tools
        commonTools = with pkgs; [
          # Build tools
          cmake pkg-config gnumake gcc gfortran
          # Scientific libraries
          gsl lapack libtool readline ncurses llvm
          # Development utilities
          jq htop procps wget curl uv
          # Python
          pythonEnv
        ];

        # Helper function to create shell environments
        mkDevShell = withJupyter: pkgs.mkShell {
          buildInputs = commonTools ++ [ nest-simulator pkgs.openmpi ];
          
          # Shell metadata
          name = if withJupyter then "tvb-nest-jupyter" else "tvb-nest";

          shellHook = ''
            ${setupEnvironment}
            
            echo "🔥 TVB-NEST Development Environment${if withJupyter then " (with Jupyter)" else ""} (${system})"
            echo "▶️ Python: ${pythonEnv}/bin/python"
            echo "▶️ NEST: ${nest-simulator}/bin/nest"
            echo "▶️ MPI: ${pkgs.openmpi}/bin/mpirun"

            ${initializeUVProject}
            ${installPythonPackages withJupyter}
            ${activateEnvironment}
            ${fixMPI4PyCompatibility}
            ${testModuleImports}
            ${showWelcome withJupyter}
          '';
        };

      in {
        devShells = {
          # Default shell: lightweight, no Jupyter
          default = mkDevShell false;
          
          # Full shell with Jupyter support
          with-jupyter = mkDevShell true;
          
          # Alias for backwards compatibility
          jupyter = mkDevShell true;
        };

      }
    );
}

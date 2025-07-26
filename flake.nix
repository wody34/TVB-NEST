{
  description = "TVB-NEST co-simulation framework with improved Nix configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        # Platform-specific configuration
        isDarwin = pkgs.stdenv.isDarwin;
        pythonLibExt = if isDarwin then "dylib" else "so";
        pythonVersion = pkgs.python3.pythonVersion;
        
        nestSrc = builtins.fetchGit {
          url = "https://github.com/sdiazpier/nest-simulator";
          rev = "4dc58f60512b8adcb6d5f1bf0eb29ffe82ae71a1";
          ref = "nest-io-dev";
        };

        # Core Python packages that should be available system-wide
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          numpy scipy cython mpi4py pip setuptools wheel
        ]);

        nest-simulator = pkgs.stdenv.mkDerivation rec {
          pname = "nest-simulator";
          version = "custom-io-dev";
          src = nestSrc;

          nativeBuildInputs = with pkgs; [ 
            cmake pkg-config which
          ];
          
          buildInputs = with pkgs; [
            gsl readline ncurses lapack libtool 
            llvm pythonEnv openmpi
          ] ++ [ pkgs.llvmPackages.openmp ];

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
          
          # Platform-specific patches if needed
          postPatch = if isDarwin then ''
            # macOS specific patches
            substituteInPlace CMakeLists.txt \
              --replace "-fopenmp" "-Xpreprocessor -fopenmp -lomp"
          '' else "";
        };

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

      in {
        devShells.default = pkgs.mkShell {
          buildInputs = commonTools ++ [ nest-simulator ] ++ (
            if isDarwin then [] else [ pkgs.openmpi ]
          );

          shellHook = ''
            set -e
            
            # Environment setup
            export PATH="${nest-simulator}/bin:$PATH"
            export PYTHONPATH="${nest-simulator}/${pythonEnv.sitePackages}:$PYTHONPATH"
            export LLVM_CONFIG=${pkgs.llvm}/bin/llvm-config
            
            # Common MPI environment setup
            export LD_LIBRARY_PATH="${nest-simulator}/lib:${nest-simulator}/lib/nest:${pkgs.openmpi}/lib:$LD_LIBRARY_PATH"
            export MPICC=${pkgs.openmpi}/bin/mpicc
            export MPICXX=${pkgs.openmpi}/bin/mpicxx
            
            ${if isDarwin then ''
              # macOS specific environment
              export OMP_NUM_THREADS=1
              echo "🍎 macOS Environment - MPI Enabled"
            '' else ''
              # Linux specific environment
              echo "🐧 Linux Environment - Full MPI Support"
            ''}

            echo "🔥 TVB-NEST Development Environment (${system})"
            echo "▶️ Python: ${pythonEnv}/bin/python"
            echo "▶️ NEST: ${nest-simulator}/bin/nest"

            # UV 프로젝트 초기화 (더 안전하게)
            if [ ! -f "pyproject.toml" ]; then
              echo "📦 UV 프로젝트 초기화"  
              uv init --python ${pythonEnv}/bin/python --no-readme
            fi

            # 필수 패키지 설치 (에러 처리 개선)
            echo "🐍 Python 패키지 설치 중..."
            
            # Core scientific packages with Jupyter
            if ! uv add numpy scipy matplotlib networkx pillow jupyter jupyterlab; then
              echo "❌ 기본 과학 패키지 설치 실패"
              exit 1
            fi
            
            # Specialized packages (optional)
            uv add pytest pyyaml numba>=0.61.0 elephant cython --quiet || echo "⚠️ 선택적 패키지 일부 설치 실패"
            
            # TVB packages (may fail, that's ok)
            uv add tvb-data tvb-gdist tvb-library --quiet || echo "⚠️ TVB 패키지 설치 실패 (수동 설치 필요할 수 있음)"

            # 가상환경 활성화
            if [ -d ".venv" ]; then
              source .venv/bin/activate
              echo "✅ UV 가상환경 활성화"
            fi

            # 중요 모듈 테스트
            echo "🧪 모듈 import 테스트"
            python -c "
import sys
print(f'Python: {sys.version}')

try:
    import nest
    print(f'✅ NEST: {getattr(nest, \"__version__\", \"OK\")}')
except ImportError as e:
    print(f'❌ NEST import 실패: {e}')

try:
    import numpy, scipy, matplotlib
    print('✅ NumPy/SciPy/Matplotlib: OK')
except ImportError as e:
    print(f'❌ 과학 패키지 import 실패: {e}')

try:
    import tvb
    print(f'✅ TVB: {getattr(tvb, \"__version__\", \"OK\")}')
except ImportError as e:
    print(f'⚠️ TVB import 실패: {e} (선택적)')
" || echo "❌ Python 모듈 테스트에서 오류 발생"

            echo ""
            echo "🎯 환경 준비 완료!"
            echo "  jupyter lab --ip=0.0.0.0 --port=8893 --no-browser --allow-root"
            echo "  🚀 MPI co-simulation 기능 사용 가능"
          '';
        };

        # macOS 전용 빠른 개발 환경
        devShells.macos-quick = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv uv cmake pkg-config gsl lapack llvm
            jq htop wget curl
          ];
          shellHook = ''
            echo "🍎 macOS 빠른 개발 환경 (NEST 빌드 없음)"
            echo "▶️ Python 패키지 개발 및 테스트용"
            
            if [ ! -f "pyproject.toml" ]; then
              uv init --python ${pythonEnv}/bin/python --no-readme
            fi
            
            uv add numpy scipy matplotlib jupyter jupyterlab networkx
            
            if [ -d ".venv" ]; then
              source .venv/bin/activate
              echo "✅ 빠른 환경 준비 완료"
            fi
          '';
        };

        # Docker 이미지 (Linux만)
        packages = if isDarwin then {} else {
          dockerImage = pkgs.dockerTools.buildLayeredImage {
            name = "tvb-nest-nix";
            tag = "latest";
            contents = [
              nest-simulator pkgs.openmpi pkgs.bash pkgs.coreutils 
              pkgs.findutils pkgs.gnugrep pkgs.gnused pkgs.gawk
              pkgs.htop pkgs.procps pkgs.jq pkgs.uv pythonEnv
            ] ++ commonTools;
            
            config = {
              Env = [
                "PATH=${nest-simulator}/bin:${pkgs.uv}/bin:${pythonEnv}/bin:${pkgs.openmpi}/bin:/bin"
                "LD_LIBRARY_PATH=${nest-simulator}/lib:${nest-simulator}/lib/nest:${pkgs.openmpi}/lib"
                "PYTHONPATH=${nest-simulator}/${pythonEnv.sitePackages}"
                "LLVM_CONFIG=${pkgs.llvm}/bin/llvm-config"
                "MPICC=${pkgs.openmpi}/bin/mpicc"
                "MPICXX=${pkgs.openmpi}/bin/mpicxx"
              ];
              WorkingDir = "/home";
              Cmd = [ "${pkgs.bash}/bin/bash" ];
            };
          };
        };
      }
    );
}

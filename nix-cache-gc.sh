nix-collect-garbage -d
nix-store --gc

rm -rf .venv
rm pyproject.toml
rm .python-version
rm uv.lock
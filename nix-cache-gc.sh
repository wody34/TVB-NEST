nix-collect-garbage -d
nix-store --gc

rm -rf .venv
rm -f pyproject.toml .python-version uv.lock



from pathlib import Path

def build_path(*parts) -> Path:
    base_dir = Path(__file__).resolve().parent.parent # /src/
    return base_dir.joinpath(*parts)
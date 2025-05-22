import os
from pathlib import Path
from dotenv import load_dotenv

def load_env():
    # 1. Pick the environment (default to 'dev' for local use)
    env = os.getenv("ENV", "dev").lower()

    # 2. Map env names to files
    env_files = {
        "prod": ".env",
        "dev": ".env_dev",
        "test": ".env_test"
    }

    env_file_name = env_files.get(env)
    if not env_file_name:
        raise ValueError(f"Unknown ENV: {env}. Expected one of {list(env_files.keys())}")

    # 3. Resolve path
    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / env_file_name

    # 4. Load it
    print(f"[config] ENV={env} -> loading {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)

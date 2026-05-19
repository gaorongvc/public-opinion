from pathlib import Path

from dotenv import load_dotenv


def load_env():
    dotenv_path = Path(".env")
    if not dotenv_path.exists():
        raise FileNotFoundError(".env is required")
    load_dotenv(dotenv_path)

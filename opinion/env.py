def load_dotenv_if_available():
    try:
        from dotenv import load_dotenv
    except Exception:
        return False
    return bool(load_dotenv())

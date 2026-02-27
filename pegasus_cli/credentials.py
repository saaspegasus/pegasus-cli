import os
from pathlib import Path

CREDENTIALS_DIR = Path.home() / ".pegasus"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials"
ENV_VAR = "PEGASUS_API_KEY"
BASE_URL_ENV_VAR = "PEGASUS_BASE_URL"
DEFAULT_BASE_URL = "https://www.saaspegasus.com"


def get_api_key() -> str | None:
    """Get the API key, checking env var first, then credentials file."""
    api_key = os.environ.get(ENV_VAR)
    if api_key:
        return api_key.strip()
    if CREDENTIALS_FILE.exists():
        return CREDENTIALS_FILE.read_text().strip()
    return None


def save_api_key(api_key: str) -> Path:
    """Save API key to ~/.pegasus/credentials. Returns the file path."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(api_key.strip() + "\n")
    CREDENTIALS_FILE.chmod(0o600)
    return CREDENTIALS_FILE


HETZNER_CREDENTIALS_FILE = CREDENTIALS_DIR / "hetzner_credentials"
HETZNER_ENV_VAR = "HETZNER_API_TOKEN"


def get_hetzner_api_key() -> str | None:
    """Get the Hetzner API token, checking env var first, then credentials file."""
    api_key = os.environ.get(HETZNER_ENV_VAR)
    if api_key:
        return api_key.strip()
    if HETZNER_CREDENTIALS_FILE.exists():
        return HETZNER_CREDENTIALS_FILE.read_text().strip()
    return None


def save_hetzner_api_key(api_key: str) -> Path:
    """Save Hetzner API token to ~/.pegasus/hetzner_credentials. Returns the file path."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    HETZNER_CREDENTIALS_FILE.write_text(api_key.strip() + "\n")
    HETZNER_CREDENTIALS_FILE.chmod(0o600)
    return HETZNER_CREDENTIALS_FILE


def get_base_url(cli_value: str | None = None) -> str:
    """Get the base URL. Priority: CLI flag > env var > default."""
    if cli_value:
        return cli_value.rstrip("/")
    env_value = os.environ.get(BASE_URL_ENV_VAR)
    if env_value:
        return env_value.rstrip("/")
    return DEFAULT_BASE_URL

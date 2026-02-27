from pegasus_cli.credentials import (
    get_api_key,
    get_base_url,
    get_hetzner_api_key,
    save_api_key,
    save_hetzner_api_key,
)


def test_save_and_read_api_key(tmp_path, monkeypatch):
    creds_dir = tmp_path / ".pegasus"
    creds_file = creds_dir / "credentials"
    monkeypatch.setattr("pegasus_cli.credentials.CREDENTIALS_DIR", creds_dir)
    monkeypatch.setattr("pegasus_cli.credentials.CREDENTIALS_FILE", creds_file)
    monkeypatch.delenv("PEGASUS_API_KEY", raising=False)

    assert get_api_key() is None

    save_api_key("test-key-123")
    assert get_api_key() == "test-key-123"
    assert oct(creds_file.stat().st_mode)[-3:] == "600"


def test_env_var_takes_precedence(tmp_path, monkeypatch):
    creds_dir = tmp_path / ".pegasus"
    creds_file = creds_dir / "credentials"
    monkeypatch.setattr("pegasus_cli.credentials.CREDENTIALS_DIR", creds_dir)
    monkeypatch.setattr("pegasus_cli.credentials.CREDENTIALS_FILE", creds_file)

    save_api_key("file-key")
    monkeypatch.setenv("PEGASUS_API_KEY", "env-key")
    assert get_api_key() == "env-key"


def test_get_base_url_default(monkeypatch):
    monkeypatch.delenv("PEGASUS_BASE_URL", raising=False)
    assert get_base_url() == "https://www.saaspegasus.com"


def test_get_base_url_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("PEGASUS_BASE_URL", "https://env.example.com")
    assert get_base_url("https://cli.example.com") == "https://cli.example.com"


def test_get_base_url_env(monkeypatch):
    monkeypatch.setenv("PEGASUS_BASE_URL", "https://env.example.com/")
    assert get_base_url() == "https://env.example.com"


def test_save_and_read_hetzner_api_key(tmp_path, monkeypatch):
    creds_dir = tmp_path / ".pegasus"
    creds_file = creds_dir / "hetzner_credentials"
    monkeypatch.setattr("pegasus_cli.credentials.CREDENTIALS_DIR", creds_dir)
    monkeypatch.setattr("pegasus_cli.credentials.HETZNER_CREDENTIALS_FILE", creds_file)
    monkeypatch.delenv("HETZNER_API_TOKEN", raising=False)

    assert get_hetzner_api_key() is None

    save_hetzner_api_key("hetzner-test-key")
    assert get_hetzner_api_key() == "hetzner-test-key"
    assert oct(creds_file.stat().st_mode)[-3:] == "600"


def test_hetzner_env_var_takes_precedence(tmp_path, monkeypatch):
    creds_dir = tmp_path / ".pegasus"
    creds_file = creds_dir / "hetzner_credentials"
    monkeypatch.setattr("pegasus_cli.credentials.CREDENTIALS_DIR", creds_dir)
    monkeypatch.setattr("pegasus_cli.credentials.HETZNER_CREDENTIALS_FILE", creds_file)

    save_hetzner_api_key("file-key")
    monkeypatch.setenv("HETZNER_API_TOKEN", "env-key")
    assert get_hetzner_api_key() == "env-key"

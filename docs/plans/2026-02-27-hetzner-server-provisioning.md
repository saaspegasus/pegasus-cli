# Hetzner Server Provisioning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `pegasus server create` command that provisions a Hetzner Cloud server and optionally updates Kamal deploy config.

**Architecture:** New `server` command group using Click, backed by an `hetzner_client.py` module wrapping the `hcloud` SDK. Hetzner credentials follow the same pattern as Pegasus credentials (env var > file). SSH keys are auto-detected from `~/.ssh/`.

**Tech Stack:** Click (CLI), hcloud SDK (Hetzner API), Rich (terminal UI), PyYAML (Kamal config parsing)

---

### Task 1: Add hcloud dependency and bump Python version

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update pyproject.toml**

In `pyproject.toml`, change `requires-python` from `">=3.9"` to `">=3.10"`, and add `"hcloud"` and `"pyyaml"` to the `dependencies` list:

```toml
requires-python = ">=3.10"
dependencies = [
    "click",
    "cookiecutter",
    "hcloud",
    "pyyaml",
    "requests",
    "rich",
]
```

**Step 2: Install dependencies**

Run: `uv sync`
Expected: Installs hcloud and pyyaml successfully.

**Step 3: Verify hcloud imports**

Run: `uv run python -c "import hcloud; print(hcloud.__version__)"`
Expected: Prints version number without errors.

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add hcloud and pyyaml dependencies, bump Python to 3.10+"
```

---

### Task 2: Add Hetzner credential helpers

**Files:**
- Modify: `pegasus_cli/credentials.py`
- Test: `tests/test_credentials.py`

**Step 1: Write the failing tests**

Add to `tests/test_credentials.py`:

```python
from pegasus_cli.credentials import (
    get_hetzner_api_key,
    save_hetzner_api_key,
)


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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_credentials.py -v -k "hetzner"`
Expected: FAIL with ImportError (functions don't exist yet).

**Step 3: Implement credential helpers**

Add to `pegasus_cli/credentials.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_credentials.py -v`
Expected: All pass (both existing and new).

**Step 5: Commit**

```bash
git add pegasus_cli/credentials.py tests/test_credentials.py
git commit -m "Add Hetzner credential helpers to credentials module"
```

---

### Task 3: Create Hetzner client module

**Files:**
- Create: `pegasus_cli/hetzner_client.py`
- Create: `tests/test_hetzner_client.py`

The Hetzner client wraps the hcloud SDK to provide three operations:
1. Validate a token (list servers as a check)
2. Ensure an SSH key exists on Hetzner (find by content or upload)
3. Create a server

**Step 1: Write the failing tests**

Create `tests/test_hetzner_client.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

from pegasus_cli.hetzner_client import HetznerClient


@pytest.fixture
def mock_hcloud():
    """Patch hcloud.Client and return the mock instance."""
    with patch("pegasus_cli.hetzner_client.hcloud.Client") as mock_cls:
        client = HetznerClient("test-token")
        yield client, mock_cls.return_value


class TestValidateToken:
    def test_validate_success(self, mock_hcloud):
        client, mock_api = mock_hcloud
        mock_api.servers.get_all.return_value = []
        # Should not raise
        client.validate_token()

    def test_validate_failure(self, mock_hcloud):
        client, mock_api = mock_hcloud
        mock_api.servers.get_all.side_effect = Exception("Unauthorized")
        with pytest.raises(Exception):
            client.validate_token()


class TestEnsureSshKey:
    def test_key_already_exists(self, mock_hcloud):
        client, mock_api = mock_hcloud
        existing_key = MagicMock()
        existing_key.name = "my-key"
        existing_key.public_key = "ssh-ed25519 AAAA testkey"
        mock_api.ssh_keys.get_all.return_value = [existing_key]

        result = client.ensure_ssh_key("my-key", "ssh-ed25519 AAAA testkey")
        assert result.name == "my-key"
        mock_api.ssh_keys.create.assert_not_called()

    def test_key_uploaded_when_missing(self, mock_hcloud):
        client, mock_api = mock_hcloud
        mock_api.ssh_keys.get_all.return_value = []
        new_key = MagicMock()
        new_key.name = "my-key"
        mock_api.ssh_keys.create.return_value = new_key

        result = client.ensure_ssh_key("my-key", "ssh-ed25519 AAAA testkey")
        assert result.name == "my-key"
        mock_api.ssh_keys.create.assert_called_once_with(
            name="my-key", public_key="ssh-ed25519 AAAA testkey"
        )


class TestCreateServer:
    def test_create_server(self, mock_hcloud):
        client, mock_api = mock_hcloud
        mock_server = MagicMock()
        mock_server.public_net.ipv4.ip = "1.2.3.4"
        mock_server.name = "my-server"
        mock_server.server_type.name = "cx22"

        mock_response = MagicMock()
        mock_response.server = mock_server
        mock_response.action = MagicMock()
        mock_api.servers.create.return_value = mock_response

        ssh_key = MagicMock()
        result = client.create_server(
            name="my-server",
            ssh_key=ssh_key,
            server_type="cx22",
            image="ubuntu-24.04",
            location="nbg1",
        )
        assert result.server.public_net.ipv4.ip == "1.2.3.4"
        mock_api.servers.create.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hetzner_client.py -v`
Expected: FAIL with ModuleNotFoundError.

**Step 3: Implement the Hetzner client**

Create `pegasus_cli/hetzner_client.py`:

```python
import hcloud
from hcloud.images import Image
from hcloud.locations import Location
from hcloud.server_types import ServerType
from hcloud.ssh_keys import SSHKey


class HetznerClient:
    def __init__(self, token: str):
        self.client = hcloud.Client(token=token)

    def validate_token(self) -> None:
        """Validate the token by making an API call. Raises on failure."""
        self.client.servers.get_all()

    def ensure_ssh_key(self, name: str, public_key: str) -> SSHKey:
        """Find an existing SSH key by content, or upload it.

        Matches by public key content (not name) to avoid duplicates.
        """
        existing_keys = self.client.ssh_keys.get_all()
        for key in existing_keys:
            if key.public_key.strip() == public_key.strip():
                return key

        return self.client.ssh_keys.create(name=name, public_key=public_key)

    def create_server(
        self,
        name: str,
        ssh_key: SSHKey,
        server_type: str = "cx22",
        image: str = "ubuntu-24.04",
        location: str = "nbg1",
    ):
        """Create a Hetzner server. Returns the create response (has .server and .action)."""
        return self.client.servers.create(
            name=name,
            server_type=ServerType(name=server_type),
            image=Image(name=image),
            location=Location(name=location),
            ssh_keys=[ssh_key],
        )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hetzner_client.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add pegasus_cli/hetzner_client.py tests/test_hetzner_client.py
git commit -m "Add Hetzner client module wrapping hcloud SDK"
```

---

### Task 4: Create the server command group with `create` subcommand

**Files:**
- Create: `pegasus_cli/server.py`
- Create: `tests/test_server.py`
- Modify: `pegasus_cli/cli.py`

This is the main task. The `server create` command ties together credentials, SSH key detection, server creation, and Kamal config updates.

**Step 1: Write the failing tests**

Create `tests/test_server.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pegasus_cli.cli import cli


def _mock_hetzner_client():
    """Create a mock HetznerClient."""
    client = MagicMock()
    mock_server = MagicMock()
    mock_server.public_net.ipv4.ip = "1.2.3.4"
    mock_server.name = "my-server"
    mock_server.server_type.name = "cx22"

    mock_response = MagicMock()
    mock_response.server = mock_server
    mock_response.action = MagicMock()
    client.create_server.return_value = mock_response

    ssh_key = MagicMock()
    ssh_key.name = "id_ed25519"
    client.ensure_ssh_key.return_value = ssh_key

    return client


class TestServerCreate:
    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_basic(self, mock_find_keys, mock_get_key, mock_client_cls):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        mock_client_cls.return_value = _mock_hetzner_client()

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "create", "my-server"])
        assert result.exit_code == 0
        assert "1.2.3.4" in result.output
        assert "ssh root@1.2.3.4" in result.output

    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_with_flags(self, mock_find_keys, mock_get_key, mock_client_cls):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        client = _mock_hetzner_client()
        mock_client_cls.return_value = client

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "server", "create", "my-server",
                "--server-type", "cx32",
                "--image", "ubuntu-22.04",
                "--location", "fsn1",
            ],
        )
        assert result.exit_code == 0
        client.create_server.assert_called_once_with(
            name="my-server",
            ssh_key=client.ensure_ssh_key.return_value,
            server_type="cx32",
            image="ubuntu-22.04",
            location="fsn1",
        )

    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_no_api_key_prompts(self, mock_find_keys):
        """When no Hetzner token is found, prompt the user."""
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        runner = CliRunner()
        with patch("pegasus_cli.server.get_hetzner_api_key", return_value=None):
            with patch("pegasus_cli.server.HetznerClient") as mock_cls:
                mock_cls.return_value = _mock_hetzner_client()
                with patch("pegasus_cli.server.save_hetzner_api_key") as mock_save:
                    mock_save.return_value = Path("~/.pegasus/hetzner_credentials")
                    result = runner.invoke(
                        cli,
                        ["server", "create", "my-server"],
                        input="my-hetzner-token\n",
                    )
                    assert result.exit_code == 0
                    mock_save.assert_called_once_with("my-hetzner-token")

    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_no_ssh_keys(self, mock_find_keys, mock_get_key):
        mock_find_keys.return_value = []
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "create", "my-server"])
        assert result.exit_code != 0
        assert "ssh-keygen" in result.output

    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_multiple_ssh_keys_prompts(
        self, mock_find_keys, mock_get_key, mock_client_cls
    ):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA key1"),
            (Path("~/.ssh/id_rsa.pub"), "ssh-rsa BBBB key2"),
        ]
        mock_client_cls.return_value = _mock_hetzner_client()

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "create", "my-server"], input="1\n")
        assert result.exit_code == 0
        assert "1.2.3.4" in result.output

    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_updates_kamal_config(
        self, mock_find_keys, mock_get_key, mock_client_cls
    ):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        mock_client_cls.return_value = _mock_hetzner_client()

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a Kamal deploy config
            Path("config").mkdir()
            Path("config/deploy.yml").write_text(
                "servers:\n  - <IP-ADDRESS>\n"
            )
            result = runner.invoke(cli, ["server", "create", "my-server"])
            assert result.exit_code == 0
            # Verify the config was updated
            config = Path("config/deploy.yml").read_text()
            assert "1.2.3.4" in config
            assert "<IP-ADDRESS>" not in config

    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_no_kamal_config_shows_docs_link(
        self, mock_find_keys, mock_get_key, mock_client_cls
    ):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        mock_client_cls.return_value = _mock_hetzner_client()

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["server", "create", "my-server"])
            assert result.exit_code == 0
            assert "docs.saaspegasus.com" in result.output
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL with ModuleNotFoundError.

**Step 3: Implement the server command**

Create `pegasus_cli/server.py`:

```python
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console

from .credentials import get_hetzner_api_key, save_hetzner_api_key
from .hetzner_client import HetznerClient

KAMAL_CONFIG_PATH = Path("config/deploy.yml")


def _find_ssh_keys() -> list[tuple[Path, str]]:
    """Find SSH public keys in ~/.ssh/. Returns list of (path, content) tuples."""
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        return []
    keys = []
    for pub_file in sorted(ssh_dir.glob("*.pub")):
        try:
            content = pub_file.read_text().strip()
            if content:
                keys.append((pub_file, content))
        except OSError:
            continue
    return keys


def _get_or_prompt_hetzner_token() -> str:
    """Get Hetzner token from env/file, or prompt the user."""
    token = get_hetzner_api_key()
    if token:
        return token

    console = Console(file=sys.stdout)
    console.print(
        "\n[bold]No Hetzner API token found.[/bold]\n"
        "\nTo create one:\n"
        "  1. Go to https://console.hetzner.cloud\n"
        "  2. Select your project\n"
        "  3. Go to Security → API Tokens\n"
        "  4. Generate a new token with Read & Write permissions\n"
    )
    token = click.prompt("Enter your Hetzner API token", hide_input=True)
    if not token.strip():
        raise click.ClickException("API token cannot be empty.")

    # Validate the token
    client = HetznerClient(token.strip())
    try:
        with console.status("Verifying token..."):
            client.validate_token()
    except Exception:
        raise click.ClickException(
            "Token validation failed. Please check your token and try again."
        )

    path = save_hetzner_api_key(token)
    click.echo(f"Token saved to {path}")
    return token.strip()


def _select_ssh_key(keys: list[tuple[Path, str]]) -> tuple[Path, str]:
    """Select an SSH key from the list. Prompts if multiple."""
    if len(keys) == 1:
        click.echo(f"Using SSH key: {keys[0][0].name}")
        return keys[0]

    click.echo("Multiple SSH keys found:")
    for i, (path, _) in enumerate(keys, 1):
        click.echo(f"  {i}. {path.name}")

    choice = click.prompt(
        "Select a key",
        type=click.IntRange(1, len(keys)),
    )
    return keys[choice - 1]


def _update_kamal_config(ip_address: str) -> bool:
    """Update config/deploy.yml with the server IP if it exists.

    Handles both simple list format and placeholder format:
      servers:
        - <IP-ADDRESS>
      servers:
        - 0.0.0.0

    Returns True if config was updated, False otherwise.
    """
    if not KAMAL_CONFIG_PATH.exists():
        return False

    try:
        content = KAMAL_CONFIG_PATH.read_text()
        data = yaml.safe_load(content)
    except Exception:
        return False

    if not isinstance(data, dict) or "servers" not in data:
        return False

    servers = data["servers"]

    # Simple list format: servers: [ip1, ip2]
    if isinstance(servers, list):
        updated = False
        for i, server in enumerate(servers):
            if isinstance(server, str) and _is_placeholder_ip(server):
                servers[i] = ip_address
                updated = True
        if updated:
            with open(KAMAL_CONFIG_PATH, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            return True

    # Role-based format: servers: {web: [ip1, ip2]}
    if isinstance(servers, dict):
        updated = False
        for role, hosts in servers.items():
            if isinstance(hosts, list):
                for i, host in enumerate(hosts):
                    if isinstance(host, str) and _is_placeholder_ip(host):
                        hosts[i] = ip_address
                        updated = True
        if updated:
            with open(KAMAL_CONFIG_PATH, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            return True

    return False


def _is_placeholder_ip(value: str) -> bool:
    """Check if a server value looks like a placeholder."""
    placeholders = {"<IP-ADDRESS>", "<ip-address>", "0.0.0.0", "<YOUR-IP>", "<your-ip>"}
    return value.strip() in placeholders


# --- CLI commands ---


@click.group()
def server():
    """Manage cloud servers."""


@server.command()
@click.argument("name")
@click.option("--server-type", default="cx22", help="Hetzner server type (default: cx22).")
@click.option("--image", default="ubuntu-24.04", help="OS image (default: ubuntu-24.04).")
@click.option("--location", default="nbg1", help="Datacenter location (default: nbg1).")
def create(name, server_type, image, location):
    """Create a new Hetzner Cloud server.

    NAME is the server name (e.g. my-app-production).
    """
    console = Console(file=sys.stdout)

    # 1. Get Hetzner token
    token = _get_or_prompt_hetzner_token()
    client = HetznerClient(token)

    # 2. Find and select SSH key
    ssh_keys = _find_ssh_keys()
    if not ssh_keys:
        raise click.ClickException(
            "No SSH public keys found in ~/.ssh/.\n"
            "Generate one with: ssh-keygen -t ed25519\n"
            "Then run this command again."
        )

    key_path, key_content = _select_ssh_key(ssh_keys)
    key_name = key_path.stem  # e.g. "id_ed25519"

    # 3. Ensure SSH key exists on Hetzner
    with console.status("Uploading SSH key to Hetzner..."):
        hetzner_key = client.ensure_ssh_key(key_name, key_content)

    # 4. Create the server
    with console.status(f"Creating server '{name}'..."):
        response = client.create_server(
            name=name,
            ssh_key=hetzner_key,
            server_type=server_type,
            image=image,
            location=location,
        )

    server_obj = response.server
    ip = server_obj.public_net.ipv4.ip

    # 5. Print results
    console.print(f"\n[bold green]Server created successfully![/bold green]\n")
    console.print(f"  Name:    {name}")
    console.print(f"  Type:    {server_type}")
    console.print(f"  Image:   {image}")
    console.print(f"  IP:      {ip}")
    console.print(f"\n  SSH:     [bold]ssh root@{ip}[/bold]\n")

    # 6. Update Kamal config if present
    if _update_kamal_config(ip):
        console.print(
            f"[bold]Updated {KAMAL_CONFIG_PATH} with server IP {ip}[/bold]"
        )
    else:
        if not KAMAL_CONFIG_PATH.exists():
            console.print(
                "Tip: For Kamal deployment setup, see "
                "https://docs.saaspegasus.com/deployment/kamal/"
            )
```

**Step 4: Register the command in cli.py**

In `pegasus_cli/cli.py`, add the import and registration:

```python
import click

from .projects import auth, projects
from .server import server
from .startapp import startapp


@click.group()
@click.version_option(package_name="pegasus-cli")
def cli():
    """Usage"""


cli.add_command(startapp)
cli.add_command(auth)
cli.add_command(projects)
cli.add_command(server)
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -v`
Expected: All pass.

**Step 6: Run the full test suite**

Run: `uv run pytest -v`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add pegasus_cli/server.py pegasus_cli/cli.py tests/test_server.py
git commit -m "Add 'pegasus server create' command for Hetzner provisioning"
```

---

### Task 5: Manual smoke test

This task cannot be automated but should be done before considering the feature complete.

**Step 1: Verify CLI help**

Run: `uv run pegasus server --help`
Expected: Shows "Manage cloud servers." and lists `create` subcommand.

Run: `uv run pegasus server create --help`
Expected: Shows name argument, --server-type, --image, --location flags with defaults.

**Step 2: Test auth flow (without a real token)**

Run: `uv run pegasus server create test-server`
Expected: Prompts for Hetzner API token with instructions.

**Step 3: (Optional) Test with a real Hetzner token**

If you have a Hetzner account, run the full flow and verify a server is created.
Remember to destroy the server afterwards to avoid charges.

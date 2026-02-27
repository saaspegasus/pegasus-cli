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
@click.option(
    "--server-type", default="cx22", help="Hetzner server type (default: cx22)."
)
@click.option(
    "--image", default="ubuntu-24.04", help="OS image (default: ubuntu-24.04)."
)
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
    console.print("\n[bold green]Server created successfully![/bold green]\n")
    console.print(f"  Name:    {name}")
    console.print(f"  Type:    {server_type}")
    console.print(f"  Image:   {image}")
    console.print(f"  IP:      {ip}")
    console.print(f"\n  SSH:     [bold]ssh root@{ip}[/bold]\n")

    # 6. Update Kamal config if present
    if _update_kamal_config(ip):
        console.print(f"[bold]Updated {KAMAL_CONFIG_PATH} with server IP {ip}[/bold]")
    else:
        if not KAMAL_CONFIG_PATH.exists():
            console.print(
                "Tip: For Kamal deployment setup, see "
                "https://docs.saaspegasus.com/deployment/kamal/"
            )

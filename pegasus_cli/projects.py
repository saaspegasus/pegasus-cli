import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

from .api_client import PegasusApiError, PegasusClient
from .credentials import get_api_key, get_base_url, save_api_key


def _get_client(base_url: str | None) -> PegasusClient:
    """Build a PegasusClient, failing with a helpful message if no API key is found."""
    api_key = get_api_key()
    if not api_key:
        raise click.ClickException(
            "No API key found. Run 'pegasus auth' to set one, "
            "or set the PEGASUS_API_KEY environment variable."
        )
    return PegasusClient(get_base_url(base_url), api_key)


# --- auth command (top-level) ---


@click.command()
@click.option("--base-url", default=None, hidden=True, help="Pegasus server URL.")
def auth(base_url):
    """Authenticate with the Pegasus server.

    Prompts for your API key and saves it to ~/.pegasus/credentials.
    """
    # If there's an existing key, let the user know
    existing = get_api_key()
    if existing:
        click.echo("An API key is already configured.")
        if not click.confirm("Do you want to replace it?"):
            return

    api_key = click.prompt("Enter your Pegasus API key", hide_input=True)
    if not api_key.strip():
        raise click.ClickException("API key cannot be empty.")

    # Verify the key works
    client = PegasusClient(get_base_url(base_url), api_key.strip())
    console = Console(file=sys.stdout)
    try:
        with console.status("Verifying API key..."):
            client.list_projects()
    except PegasusApiError as e:
        raise click.ClickException(f"API key verification failed: {e}")

    path = save_api_key(api_key)
    click.echo(f"API key saved to {path}")


# --- projects group ---


@click.group()
@click.option(
    "--base-url",
    default=None,
    envvar="PEGASUS_BASE_URL",
    help="Pegasus server URL (default: https://www.saaspegasus.com).",
)
@click.pass_context
def projects(ctx, base_url):
    """Manage your Pegasus projects."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url


_SET_TRUE = {"true", "yes", "y", "on", "1"}
_SET_FALSE = {"false", "no", "n", "off", "0"}
_SET_NULL = {"null", "none", ""}


def _parse_set_value(raw: str):
    """Best-effort type-coerce a --set value. Strings remain strings if not a known scalar."""
    lowered = raw.lower()
    if lowered in _SET_NULL:
        return None
    if lowered in _SET_TRUE:
        return True
    if lowered in _SET_FALSE:
        return False
    return raw


def _parse_set_pairs(pairs: tuple[str, ...]) -> dict:
    """Parse `--set k=v` repeated values into a dict, type-coercing values."""
    payload: dict = {}
    for pair in pairs:
        if "=" not in pair:
            raise click.ClickException(
                f"--set value {pair!r} is not in 'key=value' form."
            )
        key, _, value = pair.partition("=")
        key = key.strip()
        if not key:
            raise click.ClickException(f"--set value {pair!r} has an empty key.")
        payload[key] = _parse_set_value(value.strip())
    return payload


def _load_config_file(path: str) -> dict:
    """Load a pegasus-config.yaml-shaped file (YAML or JSON, by extension).

    If the file has a `default_context` top-level key (as real pegasus-config.yaml
    files do), unwrap it.
    """
    p = Path(path)
    if not p.exists():
        raise click.ClickException(f"Config file not found: {path}")
    raw = p.read_text()
    suffix = p.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:
            raise click.ClickException(
                "PyYAML is required to read YAML config files. "
                "Install it with: pip install pyyaml"
            ) from e
        data = yaml.safe_load(raw)
    elif suffix == ".json":
        data = json.loads(raw)
    else:
        # try YAML first (a superset of JSON for our purposes), fall back to JSON
        try:
            import yaml

            data = yaml.safe_load(raw)
        except ImportError:
            data = json.loads(raw)
    if not isinstance(data, dict):
        raise click.ClickException(f"Config file {path} did not parse to a dict.")
    if "default_context" in data and isinstance(data["default_context"], dict):
        data = data["default_context"]
    return data


def _build_payload(set_pairs: tuple[str, ...], config_file: str | None) -> dict:
    """Combine `--config-file` and `--set` inputs into a single payload dict.

    `--set` overrides values from the file.
    """
    payload: dict = {}
    if config_file:
        payload.update(_load_config_file(config_file))
    if set_pairs:
        payload.update(_parse_set_pairs(set_pairs))
    return payload


def _print_json(data) -> None:
    click.echo(json.dumps(data, indent=2, sort_keys=True, default=str))


def _print_project_config(config: dict) -> None:
    """Render a project config as a Rich table sorted alphabetically by key."""
    table = Table(title=f"Project: {config.get('project_name', '<unnamed>')}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="bold")
    for key in sorted(config.keys()):
        table.add_row(key, str(config[key]))
    console = Console(file=sys.stdout)
    console.print(table)


def _print_schema(schema: dict) -> None:
    """Render the field schema as a Rich table."""
    fields = schema.get("fields", {})
    user_tier = schema.get("user_tier")
    title = "Pegasus Project Fields"
    if user_tier:
        title += f" (your tier: {user_tier})"
    table = Table(title=title)
    table.add_column("Field", style="cyan")
    table.add_column("Type")
    table.add_column("Choices")
    table.add_column("Min Tier")
    table.add_column("R/O", justify="center")
    for name in sorted(fields.keys()):
        info = fields[name]
        choices = info.get("choices", [])
        choices_str = ", ".join(str(c) for c in choices) if choices else ""
        read_only = "✓" if info.get("read_only") else ""
        min_tier = info.get("min_tier", "")
        table.add_row(name, info.get("type", ""), choices_str, min_tier, read_only)
    console = Console(file=sys.stdout)
    console.print(table)


@projects.command(name="list")
@click.pass_context
def list_projects(ctx):
    """List your Pegasus projects."""
    client = _get_client(ctx.obj["base_url"])
    try:
        project_list = client.list_projects()
    except PegasusApiError as e:
        raise click.ClickException(str(e))

    if not project_list:
        click.echo("No projects found.")
        return

    table = _build_projects_table(project_list)
    console = Console(file=sys.stdout)
    console.print(table)


@projects.command(name="show")
@click.argument("project_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
@click.pass_context
def show_project(ctx, project_id, as_json):
    """Print a project's full configuration."""
    client = _get_client(ctx.obj["base_url"])
    try:
        config = client.get_project(project_id)
    except PegasusApiError as e:
        raise click.ClickException(str(e))
    if as_json:
        _print_json(config)
    else:
        _print_project_config(config)


@projects.command(name="fields")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
@click.pass_context
def project_fields(ctx, as_json):
    """List all available fields for project create/update, with types and choices."""
    client = _get_client(ctx.obj["base_url"])
    try:
        schema = client.get_schema()
    except PegasusApiError as e:
        raise click.ClickException(str(e))
    if as_json:
        _print_json(schema)
    else:
        _print_schema(schema)


@projects.command(name="create")
@click.option(
    "--set",
    "set_pairs",
    multiple=True,
    metavar="KEY=VALUE",
    help="Set a single field. Repeatable. e.g. --set project_slug=my_app --set use_celery=true",
)
@click.option(
    "--config-file",
    "config_file",
    default=None,
    type=click.Path(exists=False),
    help="Read settings from a pegasus-config.yaml or JSON file.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
@click.pass_context
def create_project(ctx, set_pairs, config_file, as_json):
    """Create a new project.

    project_name and project_slug are required. All other settings have model
    defaults. Combine --config-file (whole-blob input) with --set (overrides).
    """
    payload = _build_payload(set_pairs, config_file)
    if not payload:
        raise click.ClickException(
            "Nothing to do: provide --set values or --config-file."
        )
    client = _get_client(ctx.obj["base_url"])
    try:
        project = client.create_project(payload)
    except PegasusApiError as e:
        raise click.ClickException(str(e))
    if as_json:
        _print_json(project)
    else:
        click.echo(
            f"Created project {project.get('id')}: {project.get('project_name')}."
        )
        _print_project_config(project)


@projects.command(name="update")
@click.argument("project_id", type=int)
@click.option(
    "--set",
    "set_pairs",
    multiple=True,
    metavar="KEY=VALUE",
    help="Set a single field. Repeatable. e.g. --set use_celery=true --set ai_chat_mode=llm",
)
@click.option(
    "--config-file",
    "config_file",
    default=None,
    type=click.Path(exists=False),
    help="Read settings from a pegasus-config.yaml or JSON file.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
@click.pass_context
def update_project(ctx, project_id, set_pairs, config_file, as_json):
    """Update settings on an existing project.

    Only the fields you specify are changed; everything else is left alone.
    """
    payload = _build_payload(set_pairs, config_file)
    if not payload:
        raise click.ClickException(
            "Nothing to update: provide --set values or --config-file."
        )
    client = _get_client(ctx.obj["base_url"])
    try:
        project = client.update_project(project_id, payload)
    except PegasusApiError as e:
        raise click.ClickException(str(e))
    if as_json:
        _print_json(project)
    else:
        click.echo(
            f"Updated project {project.get('id')}: {project.get('project_name')}."
        )
        _print_project_config(project)


@projects.command()
@click.argument("project_id", required=False, type=int)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help="Upgrade to the latest Pegasus version before pushing.",
)
@click.option(
    "--dev",
    is_flag=True,
    default=False,
    help="Use the dev release channel (implies --upgrade).",
)
@click.option(
    "--no-upgrade",
    is_flag=True,
    default=False,
    help="Push without upgrading. Skips the interactive upgrade prompt.",
)
@click.option(
    "--pr-title",
    default=None,
    help="Custom title for the pull request (applies when a PR is created).",
)
@click.pass_context
def push(ctx, project_id, upgrade, dev, no_upgrade, pr_title):
    """Push a project to GitHub.

    If PROJECT_ID is not given, lists your projects and prompts you to choose one.
    """
    client = _get_client(ctx.obj["base_url"])

    try:
        # If no project ID, let the user pick one
        if project_id is None:
            project_id = _pick_project(client)

        # --dev implies --upgrade
        if dev:
            upgrade = True

        if no_upgrade and upgrade:
            raise click.ClickException(
                "--no-upgrade is mutually exclusive with --upgrade and --dev."
            )

        # If neither --upgrade nor --no-upgrade was given, prompt with choices
        release_channel = "stable"
        if not upgrade and not no_upgrade:
            upgrade, release_channel = _prompt_upgrade()

        if dev:
            release_channel = "dev"

        # Trigger the push
        click.echo("Triggering push to GitHub...")
        result = client.push_to_github(
            project_id,
            upgrade_to_latest=upgrade,
            release_channel=release_channel,
            pr_title=pr_title,
        )
        task_id = result["task_id"]
        version = result.get("pegasus_version", "unknown")
        click.echo(f"Task started (version {version})")

        # Poll for completion
        console = Console(file=sys.stdout)
        with Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            console=console,
            transient=False,
        ) as progress_bar:
            task = progress_bar.add_task("Starting...", total=100)
            for status in client.poll_task(project_id, task_id):
                prog = status.get("progress", {})
                description = prog.get("description", "")
                percent = int(prog.get("percent", 0))

                if description:
                    progress_bar.update(
                        task, completed=percent, description=description
                    )
                else:
                    progress_bar.update(task, completed=percent)

                if status.get("complete"):
                    progress_bar.update(task, completed=100)
                    if status.get("success"):
                        task_result = status.get("result", {})
                        pr_url = task_result.get("pull_request_url")
                        repo_url = task_result.get("repo_url")
                        if pr_url:
                            click.echo(f"\nPull request created: {pr_url}")
                        elif repo_url:
                            click.echo(f"\nRepository created: {repo_url}")
                        else:
                            click.echo("\nPush completed successfully.")
                    else:
                        error_msg = status.get("result", "Unknown error")
                        raise click.ClickException(f"Push failed: {error_msg}")

    except PegasusApiError as e:
        raise click.ClickException(str(e))


def _build_projects_table(project_list: list[dict], numbered: bool = False) -> Table:
    """Build a Rich table of projects. If numbered, adds a '#' column for selection."""
    table = Table(title="Your Projects")
    if numbered:
        table.add_column("#", style="bold", justify="right")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Name", style="bold", max_width=50)
    table.add_column("Version")
    table.add_column("Licensed", justify="center")
    table.add_column("GitHub", justify="center")

    for i, p in enumerate(project_list, 1):
        version = p.get("pegasus_version") or "unknown"
        if p.get("use_latest_version"):
            version += " (latest)"
        license_icon = "\u2705" if p.get("has_valid_license") else "\u274c"
        github_icon = "\u2705" if p.get("has_github_repo") else "\u274c"
        row = [str(p["id"]), p["name"], version, license_icon, github_icon]
        if numbered:
            row.insert(0, str(i))
        table.add_row(*row)

    return table


def _pick_project(client: PegasusClient) -> int:
    """List projects and prompt the user to pick one."""
    project_list = client.list_projects()
    if not project_list:
        raise click.ClickException("No projects found.")

    table = _build_projects_table(project_list, numbered=True)
    console = Console(file=sys.stdout)
    console.print(table)

    choice = click.prompt(
        "Select a project number",
        type=click.IntRange(1, len(project_list)),
    )
    return project_list[choice - 1]["id"]


UPGRADE_CHOICES = {
    "1": ("stable", "Upgrade to latest stable version"),
    "2": ("dev", "Upgrade to latest dev version"),
    "3": (None, "Don't upgrade"),
}


def _prompt_upgrade() -> tuple[bool, str]:
    """Prompt the user to choose an upgrade option. Returns (upgrade, release_channel)."""
    click.echo("Upgrade options:")
    for key, (_, description) in UPGRADE_CHOICES.items():
        click.echo(f"  {key}. {description}")

    choice = click.prompt(
        "Select an option",
        type=click.Choice(list(UPGRADE_CHOICES.keys())),
        default="3",
    )
    channel = UPGRADE_CHOICES[choice][0]
    if channel is None:
        return False, "stable"
    return True, channel

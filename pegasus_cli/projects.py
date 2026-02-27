import sys

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
@click.pass_context
def push(ctx, project_id, upgrade, dev):
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

        # If upgrade not specified via flags, prompt with choices
        release_channel = "stable"
        if not upgrade:
            upgrade, release_channel = _prompt_upgrade()

        if dev:
            release_channel = "dev"

        # Trigger the push
        click.echo("Triggering push to GitHub...")
        result = client.push_to_github(
            project_id, upgrade_to_latest=upgrade, release_channel=release_channel
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
    table.add_column("Name", style="bold", max_width=40)
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

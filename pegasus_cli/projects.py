import click

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
    try:
        click.echo("Verifying API key...")
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

    for p in project_list:
        version = p.get("pegasus_version") or "unknown"
        github = "github" if p.get("has_github_repo") else "no github"
        license_status = "licensed" if p.get("has_valid_license") else "unlicensed"
        click.echo(
            f"  [{p['id']}] {p['name']} (v{version}, {license_status}, {github})"
        )


@projects.command()
@click.argument("project_id", required=False, type=int)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help="Upgrade to the latest Pegasus version before pushing.",
)
@click.pass_context
def push(ctx, project_id, upgrade):
    """Push a project to GitHub.

    If PROJECT_ID is not given, lists your projects and prompts you to choose one.
    """
    client = _get_client(ctx.obj["base_url"])

    try:
        # If no project ID, let the user pick one
        if project_id is None:
            project_id = _pick_project(client)

        # Trigger the push
        click.echo("Triggering push to GitHub...")
        result = client.push_to_github(project_id, upgrade_to_latest=upgrade)
        task_id = result["task_id"]
        version = result.get("pegasus_version", "unknown")
        click.echo(f"Task started (version {version})")

        # Poll for completion
        last_description = ""
        for status in client.poll_task(project_id, task_id):
            progress = status.get("progress", {})
            description = progress.get("description", "")
            percent = progress.get("percent", 0)

            if description and description != last_description:
                click.echo(f"  [{percent:3d}%] {description}")
                last_description = description

            if status.get("complete"):
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


def _pick_project(client: PegasusClient) -> int:
    """List projects and prompt the user to pick one."""
    project_list = client.list_projects()
    if not project_list:
        raise click.ClickException("No projects found.")

    click.echo("Your projects:")
    for i, p in enumerate(project_list, 1):
        version = p.get("pegasus_version") or "unknown"
        github = "github" if p.get("has_github_repo") else "no github"
        click.echo(f"  {i}. [{p['id']}] {p['name']} (v{version}, {github})")

    choice = click.prompt(
        "Select a project number",
        type=click.IntRange(1, len(project_list)),
    )
    return project_list[choice - 1]["id"]

import secrets
import click

from pegasus_cli.monkeypatch import patch_cookiecutter
from .config import apply_shared_options, get_shared_options
from .generate import render_cookiecutter


@click.command()
@click.argument("project_name")
@apply_shared_options(get_shared_options())
def startproject(project_name, config):
    """
    Create a new Django project with the given name using local templates
    """

    context = {
        "project_name": project_name,
        "camel_case_project_name": "".join(x for x in project_name.title() if x != "_"),
        "secret_key": f"django-insecure-{secrets.token_urlsafe(32)}",
    }

    extra_cookiecutter_context = {
        "project_name": project_name,
    }
    patch_cookiecutter()
    click.echo(f"Creating project: {project_name}")

    render_cookiecutter(
        "project_template",
        ".",
        context,
        extra_cookiecutter_context,
    )
    click.echo(f"Successfully created project: {project_name}")
    click.echo("To get started:")
    click.echo(f"  cd {project_name}")
    click.echo("  python manage.py migrate")
    click.echo("  python manage.py runserver")

import click
import os
from .config import apply_shared_options, get_shared_options


@click.command()
@click.argument("project_name")
@apply_shared_options(get_shared_options())
def startproject(project_name, config):
    """
    Create a new Django project with the given name
    """
    try:
        # Use config values if present
        template_directory = config.get("template_directory", ".")

        if template_directory != "." and os.path.exists(template_directory):
            os.system(
                f"django-admin startproject {project_name} --template={template_directory}"
            )
        else:
            os.system(f"django-admin startproject {project_name}")

        click.echo(f"Successfully created project: {project_name}")
    except Exception as e:
        click.echo(f"Error creating project: {e}", err=True)

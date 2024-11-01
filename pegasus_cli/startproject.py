import click
import os


@click.command()
@click.argument("project_name")
def startproject(project_name):
    """
    Create a new Django project with the given name
    """
    try:
        os.system(f"django-admin startproject {project_name}")
        click.echo(f"Successfully created project: {project_name}")
    except Exception as e:
        click.echo(f"Error creating project: {e}", err=True)

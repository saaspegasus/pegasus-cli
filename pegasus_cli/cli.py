import click

from .startapp import startapp
from .startproject import startproject


@click.group()
@click.version_option(package_name="pegasus-cli")
def cli():
    """Usage"""


cli.add_command(startapp)
cli.add_command(startproject)

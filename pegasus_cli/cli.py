import click

from pegasus.startapp import startapp


@click.group()
@click.version_option(package_name="pegasus-cli")
def cli():
    """Usage"""


cli.add_command(startapp)

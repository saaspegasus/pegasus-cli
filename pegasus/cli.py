import click

from pegasus.startapp import startapp


@click.group()
@click.version_option()
def cli():
    """Usage"""


cli.add_command(startapp)

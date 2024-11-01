import pathlib
import yaml
import click


def load_config(ctx, param, value):
    """
    Load configuration from a YAML file.
    If no file is specified, looks for pegasus-config.yaml in current directory.
    """
    if value is None:
        default_config = pathlib.Path.cwd() / "pegasus-config.yaml"
        if default_config.exists():
            value = str(default_config)
        else:
            return {}
    try:
        with open(value, "r") as config_file:
            config = yaml.safe_load(config_file)
            if config.get("cli"):
                config = config["cli"]
            return config
    except Exception as e:
        raise click.BadParameter(f"Error loading config file: {str(e)}")


def get_shared_options():
    """
    Returns common Click options used across commands
    """
    return [
        click.option(
            "--config",
            type=click.Path(exists=True, dir_okay=False, resolve_path=True),
            callback=load_config,
            help="Path to YAML config file (default: ./pegasus-config.yml)",
        ),
    ]


def apply_shared_options(options):
    """
    Decorator to apply shared options to a command
    """

    def decorator(f):
        for option in reversed(options):
            f = option(f)
        return f

    return decorator

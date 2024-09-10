import pathlib

import click

from pegasus.templates import render_template_pack


def validate_name(ctx, param, value):
    if not value.isidentifier():
        raise click.BadParameter(
            f"'{value}' is not a valid app name. Please make sure it is a valid identifier."
        )
    return value


@click.command(name="startapp")
@click.argument("name", callback=validate_name)
@click.argument(
    "directory",
    envvar="PEGASUS_APP_DIRECTORY",
    type=click.Path(file_okay=False, exists=True, resolve_path=True),
    default=".",
)
@click.argument(
    "module_path",
    envvar="PEGASUS_MODULE_PATH",
    type=click.STRING,
    default="",
)
@click.argument(
    "model_name",
    envvar="PEGASUS_MODEL_NAME",
    type=click.STRING,
    default="",
)
def startapp(name, directory, module_path, model_name):
    """Creates a Django app directory structure for the given app name in
    the current directory or optionally in the given directory.

    \b
    NAME is the name of the Django app
    DIRECTORY is the path of the directory to create the app in. Defaults to the current directory.
    MODULE_PATH is the namespace of the module to create the app in. Defaults to "".
    MODEL_NAME is the name of the model to create. Defaults to "" (don't create a model).
    """
    app_dir = pathlib.Path(directory) / name
    if not app_dir.exists():
        app_dir.mkdir()
    elif any(app_dir.iterdir()):
        raise click.ClickException(f"target directory must be empty: {app_dir}")

    if module_path:
        app_module_path = module_path + "." + name
    else:
        app_module_path = name
    context = {
        "app_name": name,
        "camel_case_app_name": "".join(x for x in name.title() if x != "_"),
        "app_module_path": app_module_path,
        "model_name": model_name,
    }
    render_template_pack("app_template", app_dir, context)

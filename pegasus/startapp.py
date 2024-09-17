import pathlib
import yaml

import click

from pegasus.templates import render_template_pack


def validate_name(ctx, param, value):
    if not value.isidentifier():
        raise click.BadParameter(
            f"'{value}' is not a valid app name. Please make sure it is a valid identifier."
        )
    return value


def validate_model_name(ctx, param, value):
    if not value.isidentifier() or not value[0].isupper():
        raise click.BadParameter(
            f"'{value}' is not a valid Django model name. "
            "It should be a valid Python identifier and start with an uppercase letter."
        )
    return value


def load_config(ctx, param, value):
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


@click.command(name="startapp")
@click.argument("name", callback=validate_name)
@click.argument(
    "model_names",
    nargs=-1,
    envvar="PEGASUS_MODEL_NAMES",
    type=click.STRING,
    callback=lambda ctx, param, value: [
        validate_model_name(ctx, param, v) for v in value
    ],
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    callback=load_config,
    help="Path to YAML config file (default: ./pegasus-config.yml)",
)
@click.option(
    "--app-directory",
    envvar="PEGASUS_APP_DIRECTORY",
    type=click.Path(file_okay=False, exists=True, resolve_path=True),
    default=".",
    help="Directory to create the app in",
)
@click.option(
    "--module-path",
    envvar="PEGASUS_MODULE_PATH",
    type=click.STRING,
    default="",
    help="Namespace of the module to create the app in",
)
@click.option(
    "--template-directory",
    envvar="PEGASUS_TEMPLATE_DIRECTORY",
    type=click.Path(file_okay=False, exists=True, resolve_path=False),
    default=".",
    help="Directory containing templates",
)
def startapp(name, model_names, config, app_directory, module_path, template_directory):
    """Creates a Django app directory structure for the given app name in
    the current directory or optionally in the given directory.

    \b
    NAME is the name of the Django app
    MODEL_NAMES are the names of the Django models (0 or more)
    """
    # Override CLI options with config file values if present
    app_directory = config.get("app_directory", app_directory)
    module_path = config.get("module_path", module_path)

    model_names = config.get("model_names", model_names)
    model_name = model_names[0] if model_names else ""
    template_directory = config.get("template_directory", template_directory)

    app_dir = pathlib.Path(app_directory) / name
    if not app_dir.exists():
        app_dir.mkdir()

    if module_path:
        app_module_path = module_path + "." + name
    else:
        app_module_path = name
    context = {
        "app_name": name,
        "camel_case_app_name": "".join(x for x in name.title() if x != "_"),
        "app_module_path": app_module_path,
        "model_names": model_names,
        #        "model_name_lower": model_name.lower(),
    }
    render_template_pack("app_template", app_dir, context)
    print(f"Created app at {app_dir}")

    # if specified, use it, otherwise use the default directory inside the app
    if template_directory != ".":
        template_dir = pathlib.Path(template_directory) / name
    else:
        template_dir = app_dir / "templates" / name
    template_dir.mkdir(parents=True, exist_ok=True)
    render_template_pack("app_template_templates", template_dir, context)
    for model_name in model_names:
        context["model_name"] = model_name
        context["model_name_lower"] = model_name.lower()
        render_template_pack("model_templates", template_dir, context)

    print(f"Created templates at {template_dir}")

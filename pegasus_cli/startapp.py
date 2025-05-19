import pathlib
import yaml

import click

from .generate import render_cookiecutter
from .jinja import get_template_env
from .monkeypatch import patch_cookiecutter
from .ruff import run_ruff_format


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
@click.option(
    "--base-model",
    envvar="PEGASUS_BASE_MODEL",
    type=click.STRING,
    default=None,
    help="Fully-qualified base model class for the app's models, e.g. apps.utils.models.BaseModel",
)
def startapp(
    name,
    model_names,
    config,
    app_directory,
    module_path,
    template_directory,
    base_model: str | None = None,
):
    """Creates a Django app directory structure for the given app name in
    the current directory or optionally in the given directory.

    \b
    NAME is the name of the Django app
    MODEL_NAMES are the names of the Django models (0 or more)
    """
    # Override CLI options with config file values if present
    app_directory = config.get("app_directory", app_directory)
    module_path = config.get("module_path", module_path)
    base_model = config.get("base_model", base_model)
    if base_model:
        base_model_module, base_model_class = base_model.rsplit(".", 1)
    else:
        base_model_module = None
        base_model_class = None

    model_names = config.get("model_names", model_names)
    template_directory = config.get("template_directory", template_directory)
    app_dir = pathlib.Path(app_directory) / name

    # if specified, use it, otherwise use the default directory inside the app
    if template_directory != ".":
        template_dir = pathlib.Path(template_directory)
    else:
        template_dir = app_dir / "templates"

    if module_path:
        app_module_path = module_path + "." + name
    else:
        app_module_path = name

    context = {
        "app_name": name,
        "app_dir": app_dir,
        "template_dir": template_dir / name,
        "camel_case_app_name": "".join(x for x in name.title() if x != "_"),
        "app_module_path": app_module_path,
        "model_names": model_names,
        "base_model": base_model,
        "base_model_module": base_model_module,
        "base_model_class": base_model_class,
    }
    use_teams = config.get("use_teams", False)
    context.update(_get_team_context(use_teams))

    css_framework = config.get("css_framework", "tailwind")
    context.update(_get_css_framework_context(css_framework))

    patch_cookiecutter()

    extra_cookiecutter_context = {"app_name": name, "template_dir_name": name}
    render_cookiecutter(
        "app_template",
        app_directory,
        context,
        extra_cookiecutter_context,
    )

    render_cookiecutter(
        "app_template_templates",
        template_dir,
        context,
        extra_cookiecutter_context,
    )

    for model_name in model_names:
        context["model_name"] = model_name
        context["model_name_lower"] = model_name.lower()
        render_cookiecutter(
            "model_templates",
            template_dir,
            context,
            extra_cookiecutter_context,
        )

    run_ruff_format(app_dir)

    env = get_template_env()
    output = env.get_template("internal/cli_output.txt").render(context)
    print(output)


def _get_team_context(use_teams: bool) -> dict:
    if use_teams:
        view_decorator_module = "apps.teams.decorators"
        view_decorator_function = "login_and_team_required"
        extra_view_param = "team_slug"
        extra_view_param_type = "str"
        extra_view_param_value = "request.team.slug"
        extra_model_param_value = "self.team.slug"
        extra_view_args = (
            f", {extra_view_param}: {extra_view_param_type}"  # todo: this is gross
        )
        extra_url_args = f" {extra_view_param_value}"  # todo: and so is this
    else:
        view_decorator_module = "django.contrib.auth.decorators"
        view_decorator_function = "login_required"
        extra_view_param = None
        extra_view_param_type = None
        extra_view_param_value = None
        extra_model_param_value = None
        extra_view_args = ""
        extra_url_args = ""

    return {
        "use_teams": use_teams,
        "view_decorator_module": view_decorator_module,
        "view_decorator_function": view_decorator_function,
        "extra_view_param": extra_view_param,
        "extra_view_param_type": extra_view_param_type,
        "extra_view_param_value": extra_view_param_value,
        "extra_model_param_value": extra_model_param_value,
        "extra_view_args": extra_view_args,
        "extra_url_args": extra_url_args,
    }


def _get_css_framework_context(css_framework: str) -> dict:
    extra_context = {
        "css_framework": css_framework,
    }
    if css_framework == "tailwind":
        extra_context.update(
            {
                "modal_open_class": "modal-open",
                "modal_background_class": "modal-backdrop",
                "modal_content_class": "modal-box",
            }
        )
    elif css_framework == "bulma":
        extra_context.update(
            {
                "modal_open_class": "is-active",
                "modal_background_class": "modal-background",
                "modal_content_class": "modal-content box",
            }
        )
    elif css_framework == "bootstrap":
        extra_context.update(
            {
                "modal_open_class": "modal-open",
                "modal_background_class": "modal-backdrop",
            }
        )
    else:
        raise ValueError(f"Invalid CSS framework: {css_framework}")
    return extra_context

import ast
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


def find_settings_from_manage_py(manage_py_path: pathlib.Path) -> "pathlib.Path | None":
    """Parse manage.py with ast and return the path to the settings file.

    Handles two common patterns:
      os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
      os.environ["DJANGO_SETTINGS_MODULE"] = "myproject.settings"

    Returns the resolved Path if the file exists, otherwise None.
    """
    try:
        source = manage_py_path.read_text()
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return None

    module_name = None
    for node in ast.walk(tree):
        # os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "setdefault"
            and isinstance(node.value.func.value, ast.Attribute)
            and node.value.func.value.attr == "environ"
            and len(node.value.args) == 2
            and isinstance(node.value.args[0], ast.Constant)
            and node.value.args[0].value == "DJANGO_SETTINGS_MODULE"
            and isinstance(node.value.args[1], ast.Constant)
        ):
            module_name = node.value.args[1].value
            break

        # os.environ["DJANGO_SETTINGS_MODULE"] = "myproject.settings"
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Subscript)
            and isinstance(node.targets[0].value, ast.Attribute)
            and node.targets[0].value.attr == "environ"
            and isinstance(node.targets[0].slice, ast.Constant)
            and node.targets[0].slice.value == "DJANGO_SETTINGS_MODULE"
            and isinstance(node.value, ast.Constant)
        ):
            module_name = node.value.value
            break

    if not module_name:
        return None

    settings_path = manage_py_path.parent / pathlib.Path(
        module_name.replace(".", "/")
    ).with_suffix(".py")
    return settings_path if settings_path.exists() else None


def add_to_installed_apps(settings_path: str, app_config: str) -> bool:
    """Add app_config to INSTALLED_APPS (or PROJECT_APPS) in the given settings file.

    Uses the ast library to locate the list and inserts the new entry before the
    closing bracket.  Returns True if the entry was inserted, False if no suitable
    list assignment was found.
    """
    path = pathlib.Path(settings_path)
    source = path.read_text()
    tree = ast.parse(source)

    for var_name in ("PROJECT_APPS", "INSTALLED_APPS"):
        list_node = _find_list_assignment(tree, var_name)
        if list_node is not None:
            if _list_contains_string(list_node, app_config):
                return True
            modified = _insert_into_ast_list(source, list_node, f'"{app_config}"')
            path.write_text(modified)
            return True

    return False


def add_to_urlpatterns(
    urls_path: str, app_name: str, app_module_path: str, use_teams: bool
) -> bool:
    """Add a path() entry for the new app to urlpatterns (or team_urlpatterns) in urls_path.

    Returns True if the entry was inserted, False if no suitable list assignment was found.
    """
    path = pathlib.Path(urls_path)
    source = path.read_text()
    tree = ast.parse(source)

    var_name = "team_urlpatterns" if use_teams else "urlpatterns"
    list_node = _find_list_assignment(tree, var_name)
    if list_node is None:
        return False

    if _list_contains_string(list_node, f"{app_module_path}.urls"):
        return True
    entry = f'path("{app_name}/", include("{app_module_path}.urls"))'
    modified = _insert_into_ast_list(source, list_node, entry)
    path.write_text(modified)
    return True


def _list_contains_string(list_node: ast.List, value: str) -> bool:
    """Check whether any string constant in the AST list contains *value*."""
    for elt in ast.walk(list_node):
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            if value in elt.value:
                return True
    return False


def _find_list_assignment(tree: ast.Module, var_name: str) -> "ast.List | None":
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    if isinstance(node.value, ast.List):
                        return node.value
    return None


def _insert_into_ast_list(source: str, list_node: ast.List, entry: str) -> str:
    """Insert entry (raw text) as a new element into the list, before the closing ']'."""
    lines = source.splitlines(keepends=True)
    end_line_idx = list_node.end_lineno - 1  # 0-indexed
    end_col = list_node.end_col_offset  # column index right after ']'
    line = lines[end_line_idx]

    if list_node.lineno == list_node.end_lineno:
        # Single-line list: insert before ']'
        sep = ", " if list_node.elts else ""
        lines[end_line_idx] = (
            line[: end_col - 1] + f"{sep}{entry}" + line[end_col - 1 :]
        )
    else:
        # Multi-line list: insert a new line before the line containing ']'
        bracket_indent = line[: end_col - 1]
        item_indent = bracket_indent + "    "
        new_line = f"{item_indent}{entry},\n"
        lines[end_line_idx] = new_line + line

    return "".join(lines)


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
@click.option(
    "--django-settings",
    envvar="PEGASUS_DJANGO_SETTINGS",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    default=None,
    help="Path to Django settings.py to automatically add the app to INSTALLED_APPS",
)
def startapp(
    name,
    model_names,
    config,
    app_directory,
    module_path,
    template_directory,
    base_model: str | None = None,
    django_settings: str | None = None,
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
    django_settings = config.get("django_settings", django_settings)
    if not django_settings:
        manage_py = pathlib.Path.cwd() / "manage.py"
        resolved = find_settings_from_manage_py(manage_py)
        if resolved:
            django_settings = str(resolved)
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

    app_config_string = f"{app_module_path}.apps.{context['camel_case_app_name']}Config"
    settings_updated = False
    urls_updated = False
    if django_settings:
        settings_updated = add_to_installed_apps(django_settings, app_config_string)
        urls_path = pathlib.Path(django_settings).parent / "urls.py"
        if urls_path.exists():
            urls_updated = add_to_urlpatterns(
                str(urls_path), name, app_module_path, use_teams
            )

    context["app_config_string"] = app_config_string
    context["settings_updated"] = settings_updated
    context["urls_updated"] = urls_updated
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

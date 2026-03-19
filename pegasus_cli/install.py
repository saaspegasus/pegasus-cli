import ast
import pathlib


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
        module_name = _match_environ_setdefault(node) or _match_environ_assignment(node)
        if module_name:
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


def _match_environ_setdefault(node: ast.AST) -> "str | None":
    """Match ``os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mod.settings")``
    and return the module string, or None."""
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
        return node.value.args[1].value
    return None


def _match_environ_assignment(node: ast.AST) -> "str | None":
    """Match ``os.environ["DJANGO_SETTINGS_MODULE"] = "mod.settings"``
    and return the module string, or None."""
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
        return node.value.value
    return None


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

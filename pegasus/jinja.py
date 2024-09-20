import pathlib

from jinja2 import Environment, FileSystemLoader, select_autoescape

START = "<"
END = ">"
TEMPLATE_BASE = pathlib.Path(__file__).parent / "templates"


def get_template_env(search_path=TEMPLATE_BASE):
    return Environment(
        loader=FileSystemLoader(search_path),
        autoescape=select_autoescape(),
        # Use different delimiters to avoid conflicts with Django templates
        block_start_string=f"{START}%",
        block_end_string=f"%{END}",
        variable_start_string=f"{START}{START}",
        variable_end_string=f"{END}{END}",
        comment_start_string=f"{START}#",
        comment_end_string=f"#{END}",
    )


def get_filname_template_env():
    return Environment(
        variable_start_string="^^",
        variable_end_string="^^",
    )

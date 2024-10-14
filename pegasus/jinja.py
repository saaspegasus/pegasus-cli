import pathlib

from jinja2 import Environment, FileSystemLoader, select_autoescape

START = "<"
END = ">"
OSTART = "{"
OEND = "}"
TEMPLATE_BASE = pathlib.Path(__file__).parent / "templates"

ENV_KWARGS = dict(
    block_start_string=f"{START}%",
    block_end_string=f"%{END}",
    variable_start_string=f"{START}{START}",
    variable_end_string=f"{END}{END}",
    comment_start_string=f"{START}#",
    comment_end_string=f"#{END}",
)

FILENAME_ENV_KWARGS = dict(
    block_start_string=f"{OSTART}%",
    block_end_string=f"%{OEND}",
    variable_start_string=f"{OSTART}{OSTART}",
    variable_end_string=f"{OEND}{OEND}",
    comment_start_string=f"{OSTART}#",
    comment_end_string=f"#{OEND}",
)


def get_template_env(search_path=TEMPLATE_BASE):
    return Environment(
        loader=FileSystemLoader(search_path),
        autoescape=select_autoescape(),
        # Use different delimiters to avoid conflicts with Django templates
        **ENV_KWARGS,
    )

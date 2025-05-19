from cookiecutter.generate import generate_files

from .jinja import ENV_KWARGS, TEMPLATE_BASE


def render_cookiecutter(
    template_pack,
    output_dir,
    context,
    extra_cookiecutter_context=None,
    template_base=TEMPLATE_BASE,
):
    repo_dir = template_base / template_pack

    generate_files(
        repo_dir=repo_dir,
        context={
            **context,
            "cookiecutter": {
                "_jinja2_env_vars": ENV_KWARGS,
                **extra_cookiecutter_context,
            },
        },
        overwrite_if_exists=True,
        skip_if_file_exists=False,
        output_dir=output_dir,
        accept_hooks=True,
        keep_project_on_failure=True,
    )

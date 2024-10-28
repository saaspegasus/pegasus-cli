"""Monkeypatching for cookiecutter to use a different Jinja environment for rendering filenames.
This makes it possible to use different delimiters for Jinja templates in filenames vs file content.

The main goal is to avoid conflicts with Django templates. However,
using `<` and `>` for filenames does not work on Windows so we use `<` and `>` for file contents and
`{` and `}` for filenames.
"""
from .jinja import FILENAME_ENV_KWARGS


def patch_cookiecutter():
    patch_find_template()
    patch_create_env_with_context()


def patch_find_template():
    """Patch the Jinja env for this method to use the overlay env.
    This is called when cookiecutter is searching for the template directory."""
    from cookiecutter import generate

    def new_find_template(repo, env, find_template=generate.find_template):
        filename_env = env.overlay(**FILENAME_ENV_KWARGS)
        return find_template(repo, filename_env)

    generate.find_template = new_find_template


def patch_create_env_with_context():
    """Patch the `from_string` method of the Jinja env to use the overlay env.
    The `from_string` method is used when rendering filenames.
    """
    from cookiecutter import generate

    def new_create_env_with_context(
        context, create_env_with_context=generate.create_env_with_context
    ):
        env = create_env_with_context(context)
        filename_env = env.overlay(**FILENAME_ENV_KWARGS)
        env.from_string = filename_env.from_string
        return env

    generate.create_env_with_context = new_create_env_with_context

from pegasus.jinja import OVERLAY_ENV_KWARGS


def patch_cookiecutter():
    patch_find_template()
    patch_create_env_with_context()


def patch_find_template():
    """Patch the Jinja env for this method to use the overlay env.
    This is called when cookiecutter is searching for the template directory."""
    from cookiecutter import generate

    def new_find_template(repo, env, find_template=generate.find_template):
        new_env = env.overlay(**OVERLAY_ENV_KWARGS)
        return find_template(repo, new_env)

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
        overlay_env = env.overlay(**OVERLAY_ENV_KWARGS)
        env.from_string = overlay_env.from_string
        return env

    generate.create_env_with_context = new_create_env_with_context

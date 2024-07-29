import dataclasses
import os
import pathlib

from pegasus.jinja import TEMPLATE_BASE, get_template_env


def render_template_pack(
    pack_name,
    app_dir: pathlib.Path,
    context: dict,
    templates_path: pathlib.Path = TEMPLATE_BASE,
):
    """Create the template pack directory structure and render the templates with the given context.

    Args:
        pack_name (str): The name of the template pack to render
        app_dir (pathlib.Path): The directory to render the templates in
        context (dict): The context to render the templates with
        templates_path (pathlib.Path): The base path to search for template packs
    """
    env = get_template_env(templates_path)

    for template in get_templates(pack_name, templates_path):
        if template.is_dir():
            template.mkdir(app_dir)
            continue

        j2_template = env.get_template(template.template_name)
        content = j2_template.render(context)
        with template.get_target_path(app_dir).open("w") as f:
            f.write(content)


def get_templates(template_pack, templates_path=TEMPLATE_BASE):
    """Yield all templates in the given template pack.

    Args:
        template_pack (str): The name of the template pack to get templates from
        templates_path (pathlib.Path): The base path to search for template packs
    """
    template_base = templates_path / template_pack
    for file in template_base.glob("**/*"):
        yield TemplatePackFile(
            template_pack=template_pack,
            filename=str(file.relative_to(template_base)),
            path=file,
        )


@dataclasses.dataclass
class TemplatePackFile:
    template_pack: str
    filename: str
    path: pathlib.Path

    def is_dir(self):
        return self.path.is_dir()

    def mkdir(self, base):
        base_path = base / self.filename
        base_path.mkdir()

    @property
    def template_name(self):
        # Jinja expects forward slashes as path separators for templates
        template_name = self.filename.replace(os.path.sep, "/")
        return f"{self.template_pack}/{template_name}"

    def get_target_path(self, base):
        return base / self.filename.removesuffix(".j2")

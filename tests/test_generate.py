import pathlib

from pegasus_cli.generate import render_cookiecutter
from pegasus_cli.monkeypatch import patch_cookiecutter

TEMPLATES_PATH = pathlib.Path(__file__).parent

patch_cookiecutter()


def test_generate(tmpdir):
    render_cookiecutter(
        "template",
        tmpdir,
        {"app_name": "test_app"},
        extra_cookiecutter_context={"dir_name": "test_dir"},
        template_base=TEMPLATES_PATH,
    )

    generated_files = {
        f.relto(tmpdir): f.read()
        for f in tmpdir.visit(fil=lambda x: x.check(file=True))
    }
    expected = {
        "test_dir/readme.md": "Hello test_app!\n",
    }
    assert generated_files == expected

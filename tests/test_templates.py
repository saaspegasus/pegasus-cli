import pathlib

from pegasus.templates import render_template_pack

TEMPLATES_PATH = pathlib.Path(__file__).parent / "templates"


def test_render_template_pack(tmpdir):
    render_template_pack(
        "test_pack",
        tmpdir,
        {
            "context_var1": "test1",
            "context_var2": "test2",
            "context_var3": "test3",
        },
        templates_path=TEMPLATES_PATH,
    )

    generated_files = {
        f.relto(tmpdir): f.read()
        for f in tmpdir.visit(fil=lambda x: x.check(file=True))
    }
    expected = {
        "empty.txt": "",
        "file.txt": "test1\n",
        "sub/subfile.txt": "test2\n",
        "sub/subsub/subsubfile.txt": "test3\n",
    }
    assert generated_files == expected

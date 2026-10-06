from pathlib import Path

from click.testing import CliRunner

from pegasus_cli.migrate_css import migrate_css

TAILWIND_CSS = """\
.pg-link {
  @apply text-blue-500 hover:text-blue-800;
}

.pg-text-muted {
  @apply text-base-content/70;
}
"""


def _write(path: str, content: str):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _setup_css():
    _write("assets/styles/pegasus/tailwind.css", TAILWIND_CSS)


def test_migrates_python_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _setup_css()
        _write(
            "apps/web/templatetags/form_tags.py",
            'TEMPLATE = """<small class="pg-text-muted">help</small>"""\n',
        )
        result = runner.invoke(migrate_css, [])
        assert result.exit_code == 0, result.output
        assert "apps/web/templatetags/form_tags.py" in result.output
        assert (
            'class="text-base-content/70"'
            in Path("apps/web/templatetags/form_tags.py").read_text()
        )


def test_scans_frontend_by_default_but_skips_node_modules():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _setup_css()
        _write("frontend/src/pages/Login.tsx", '<a className="pg-link">x</a>\n')
        vendored = '<a className="pg-link">x</a>\n'
        _write("frontend/node_modules/somelib/index.js", vendored)
        result = runner.invoke(migrate_css, [])
        assert result.exit_code == 0, result.output
        assert (
            'className="text-blue-500 hover:text-blue-800"'
            in Path("frontend/src/pages/Login.tsx").read_text()
        )
        assert Path("frontend/node_modules/somelib/index.js").read_text() == vendored
        assert "node_modules" not in result.output


def test_reports_complex_and_undefined_classes_separately():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write(
            "assets/styles/pegasus/tailwind.css",
            TAILWIND_CSS
            + "\n.pg-select {\n  & select {\n    @apply select w-full;\n  }\n}\n",
        )
        _write(
            "templates/form.html",
            '<div class="pg-select"><a class="pg-link pg-mystery">x</a></div>\n',
        )
        result = runner.invoke(migrate_css, ["--dry-run"])
        assert result.exit_code == 0, result.output
        complex_section, undefined_section = result.output.split("no definition")
        assert "must be migrated by hand" in complex_section
        assert "pg-select (1 file)" in complex_section
        assert "pg-mystery (1 file)" in undefined_section
        assert "pg-select" not in undefined_section

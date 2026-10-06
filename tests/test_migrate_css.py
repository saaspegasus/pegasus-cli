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

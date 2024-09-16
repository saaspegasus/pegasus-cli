from click.testing import CliRunner
from pegasus.cli import cli


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        print("cli is")
        print(cli)
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert result.output.startswith("cli, version ")

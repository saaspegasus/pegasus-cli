from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pegasus_cli.cli import cli


def _mock_hetzner_client():
    """Create a mock HetznerClient."""
    client = MagicMock()
    mock_server = MagicMock()
    mock_server.public_net.ipv4.ip = "1.2.3.4"
    mock_server.name = "my-server"
    mock_server.server_type.name = "cx22"

    mock_response = MagicMock()
    mock_response.server = mock_server
    mock_response.action = MagicMock()
    client.create_server.return_value = mock_response

    ssh_key = MagicMock()
    ssh_key.name = "id_ed25519"
    client.ensure_ssh_key.return_value = ssh_key

    return client


class TestServerCreate:
    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_basic(self, mock_find_keys, mock_get_key, mock_client_cls):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        mock_client_cls.return_value = _mock_hetzner_client()

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "create", "my-server"])
        assert result.exit_code == 0
        assert "1.2.3.4" in result.output
        assert "ssh root@1.2.3.4" in result.output

    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_with_flags(self, mock_find_keys, mock_get_key, mock_client_cls):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        client = _mock_hetzner_client()
        mock_client_cls.return_value = client

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "server",
                "create",
                "my-server",
                "--server-type",
                "cx32",
                "--image",
                "ubuntu-22.04",
                "--location",
                "fsn1",
            ],
        )
        assert result.exit_code == 0
        client.create_server.assert_called_once_with(
            name="my-server",
            ssh_key=client.ensure_ssh_key.return_value,
            server_type="cx32",
            image="ubuntu-22.04",
            location="fsn1",
        )

    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_no_api_key_prompts(self, mock_find_keys):
        """When no Hetzner token is found, prompt the user."""
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        runner = CliRunner()
        with patch("pegasus_cli.server.get_hetzner_api_key", return_value=None):
            with patch("pegasus_cli.server.HetznerClient") as mock_cls:
                mock_cls.return_value = _mock_hetzner_client()
                with patch("pegasus_cli.server.save_hetzner_api_key") as mock_save:
                    mock_save.return_value = Path("~/.pegasus/hetzner_credentials")
                    result = runner.invoke(
                        cli,
                        ["server", "create", "my-server"],
                        input="my-hetzner-token\n",
                    )
                    assert result.exit_code == 0
                    mock_save.assert_called_once_with("my-hetzner-token")

    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_no_ssh_keys(self, mock_find_keys, mock_get_key):
        mock_find_keys.return_value = []
        runner = CliRunner()
        result = runner.invoke(cli, ["server", "create", "my-server"])
        assert result.exit_code != 0
        assert "ssh-keygen" in result.output

    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_multiple_ssh_keys_prompts(
        self, mock_find_keys, mock_get_key, mock_client_cls
    ):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA key1"),
            (Path("~/.ssh/id_rsa.pub"), "ssh-rsa BBBB key2"),
        ]
        mock_client_cls.return_value = _mock_hetzner_client()

        runner = CliRunner()
        result = runner.invoke(cli, ["server", "create", "my-server"], input="1\n")
        assert result.exit_code == 0
        assert "1.2.3.4" in result.output

    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_updates_kamal_config(
        self, mock_find_keys, mock_get_key, mock_client_cls
    ):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        mock_client_cls.return_value = _mock_hetzner_client()

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a Kamal deploy config
            Path("config").mkdir()
            Path("config/deploy.yml").write_text("servers:\n  - <IP-ADDRESS>\n")
            result = runner.invoke(cli, ["server", "create", "my-server"])
            assert result.exit_code == 0
            # Verify the config was updated
            config = Path("config/deploy.yml").read_text()
            assert "1.2.3.4" in config
            assert "<IP-ADDRESS>" not in config

    @patch("pegasus_cli.server.HetznerClient")
    @patch("pegasus_cli.server.get_hetzner_api_key", return_value="test-token")
    @patch("pegasus_cli.server._find_ssh_keys")
    def test_create_no_kamal_config_shows_docs_link(
        self, mock_find_keys, mock_get_key, mock_client_cls
    ):
        mock_find_keys.return_value = [
            (Path("~/.ssh/id_ed25519.pub"), "ssh-ed25519 AAAA testkey")
        ]
        mock_client_cls.return_value = _mock_hetzner_client()

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["server", "create", "my-server"])
            assert result.exit_code == 0
            assert "docs.saaspegasus.com" in result.output

from unittest.mock import MagicMock, patch

import pytest

from pegasus_cli.hetzner_client import HetznerClient


@pytest.fixture
def mock_hcloud():
    """Patch hcloud.Client and return the mock instance."""
    with patch("pegasus_cli.hetzner_client.hcloud.Client") as mock_cls:
        client = HetznerClient("test-token")
        yield client, mock_cls.return_value


class TestValidateToken:
    def test_validate_success(self, mock_hcloud):
        client, mock_api = mock_hcloud
        mock_api.servers.get_all.return_value = []
        # Should not raise
        client.validate_token()

    def test_validate_failure(self, mock_hcloud):
        client, mock_api = mock_hcloud
        mock_api.servers.get_all.side_effect = Exception("Unauthorized")
        with pytest.raises(Exception):
            client.validate_token()


class TestEnsureSshKey:
    def test_key_already_exists(self, mock_hcloud):
        client, mock_api = mock_hcloud
        existing_key = MagicMock()
        existing_key.name = "my-key"
        existing_key.public_key = "ssh-ed25519 AAAA testkey"
        mock_api.ssh_keys.get_all.return_value = [existing_key]

        result = client.ensure_ssh_key("my-key", "ssh-ed25519 AAAA testkey")
        assert result.name == "my-key"
        mock_api.ssh_keys.create.assert_not_called()

    def test_key_uploaded_when_missing(self, mock_hcloud):
        client, mock_api = mock_hcloud
        mock_api.ssh_keys.get_all.return_value = []
        new_key = MagicMock()
        new_key.name = "my-key"
        mock_api.ssh_keys.create.return_value = new_key

        result = client.ensure_ssh_key("my-key", "ssh-ed25519 AAAA testkey")
        assert result.name == "my-key"
        mock_api.ssh_keys.create.assert_called_once_with(
            name="my-key", public_key="ssh-ed25519 AAAA testkey"
        )


class TestCreateServer:
    def test_create_server(self, mock_hcloud):
        client, mock_api = mock_hcloud
        mock_server = MagicMock()
        mock_server.public_net.ipv4.ip = "1.2.3.4"
        mock_server.name = "my-server"
        mock_server.server_type.name = "cx22"

        mock_response = MagicMock()
        mock_response.server = mock_server
        mock_response.action = MagicMock()
        mock_api.servers.create.return_value = mock_response

        ssh_key = MagicMock()
        result = client.create_server(
            name="my-server",
            ssh_key=ssh_key,
            server_type="cx22",
            image="ubuntu-24.04",
            location="nbg1",
        )
        assert result.server.public_net.ipv4.ip == "1.2.3.4"
        mock_api.servers.create.assert_called_once()

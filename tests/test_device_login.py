from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from pegasus_cli.api_client import PegasusApiError
from pegasus_cli.cli import cli
from pegasus_cli.device_login import start_device_login, wait_for_api_key

BASE_URL = "https://pegasus.test"

START_RESPONSE = {
    "device_code": "secret-device-code",
    "user_code": "BCDF-GHJK",
    "verification_uri": f"{BASE_URL}/cli-auth/",
    "verification_uri_complete": f"{BASE_URL}/cli-auth/?code=BCDF-GHJK",
    "expires_in": 600,
    "interval": 5,
}


def _response(status_code, data):
    response = MagicMock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    response.json.return_value = data
    return response


def _no_sleep(_seconds):
    pass


class TestStartDeviceLogin:
    @patch("pegasus_cli.device_login.requests.post")
    def test_returns_server_response(self, mock_post):
        mock_post.return_value = _response(200, START_RESPONSE)
        assert start_device_login(BASE_URL, "laptop") == START_RESPONSE
        mock_post.assert_called_once_with(
            f"{BASE_URL}/cli-auth/api/start/",
            json={"client_name": "laptop"},
            timeout=30,
        )

    @patch("pegasus_cli.device_login.requests.post")
    def test_old_server_suggests_with_key(self, mock_post):
        mock_post.return_value = _response(404, {})
        with pytest.raises(PegasusApiError, match="--with-key"):
            start_device_login(BASE_URL, "laptop")


class TestWaitForApiKey:
    @patch("pegasus_cli.device_login.requests.post")
    def test_polls_until_approved(self, mock_post):
        mock_post.side_effect = [
            _response(400, {"error": "authorization_pending"}),
            _response(400, {"error": "authorization_pending"}),
            _response(200, {"api_key": "new-key", "email": "me@example.com"}),
        ]
        result = wait_for_api_key(BASE_URL, "code", 5, 600, sleep=_no_sleep)
        assert result == {"api_key": "new-key", "email": "me@example.com"}
        assert mock_post.call_count == 3

    @patch("pegasus_cli.device_login.requests.post")
    def test_slow_down_increases_interval(self, mock_post):
        mock_post.side_effect = [
            _response(400, {"error": "slow_down"}),
            _response(200, {"api_key": "new-key", "email": "me@example.com"}),
        ]
        sleeps = []
        wait_for_api_key(BASE_URL, "code", 5, 600, sleep=sleeps.append)
        assert sleeps == [5, 10]

    @pytest.mark.parametrize(
        "error,message",
        [
            ("access_denied", "denied"),
            ("expired_token", "expired"),
            ("invalid_grant", "expired"),
        ],
    )
    @patch("pegasus_cli.device_login.requests.post")
    def test_terminal_errors(self, mock_post, error, message):
        mock_post.return_value = _response(400, {"error": error})
        with pytest.raises(PegasusApiError, match=message):
            wait_for_api_key(BASE_URL, "code", 5, 600, sleep=_no_sleep)

    @patch("pegasus_cli.device_login.requests.post")
    def test_gives_up_after_expiry(self, mock_post):
        mock_post.return_value = _response(400, {"error": "authorization_pending"})
        with pytest.raises(PegasusApiError, match="expired"):
            wait_for_api_key(BASE_URL, "code", 5, 0, sleep=_no_sleep)
        mock_post.assert_not_called()


class TestLoginCommand:
    @patch("pegasus_cli.projects.webbrowser.open")
    @patch(
        "pegasus_cli.projects.save_api_key",
        return_value="/home/me/.pegasus/credentials",
    )
    @patch("pegasus_cli.projects.wait_for_api_key")
    @patch("pegasus_cli.projects.start_device_login", return_value=START_RESPONSE)
    @patch("pegasus_cli.projects.get_api_key", return_value=None)
    def test_browser_login_saves_key(
        self, _get_key, mock_start, mock_wait, mock_save, mock_open
    ):
        mock_wait.return_value = {"api_key": "new-key", "email": "me@example.com"}
        result = CliRunner().invoke(cli, ["auth", "login"])
        assert result.exit_code == 0, result.output
        assert START_RESPONSE["verification_uri_complete"] in result.output
        assert "BCDF-GHJK" in result.output
        assert "Logged in as me@example.com" in result.output
        mock_open.assert_called_once_with(START_RESPONSE["verification_uri_complete"])
        mock_save.assert_called_once_with("new-key")

    @patch("pegasus_cli.projects.webbrowser.open")
    @patch("pegasus_cli.projects.save_api_key")
    @patch("pegasus_cli.projects.wait_for_api_key")
    @patch("pegasus_cli.projects.start_device_login", return_value=START_RESPONSE)
    @patch("pegasus_cli.projects.get_api_key", return_value=None)
    def test_bare_auth_uses_browser_login(
        self, _get_key, mock_start, mock_wait, mock_save, mock_open
    ):
        mock_wait.return_value = {"api_key": "new-key", "email": "me@example.com"}
        result = CliRunner().invoke(cli, ["auth"])
        assert result.exit_code == 0, result.output
        mock_start.assert_called_once()

    @patch("pegasus_cli.projects.webbrowser.open")
    @patch("pegasus_cli.projects.save_api_key")
    @patch("pegasus_cli.projects.wait_for_api_key")
    @patch("pegasus_cli.projects.start_device_login", return_value=START_RESPONSE)
    @patch("pegasus_cli.projects.get_api_key", return_value=None)
    def test_no_browser_flag(
        self, _get_key, mock_start, mock_wait, mock_save, mock_open
    ):
        mock_wait.return_value = {"api_key": "new-key", "email": "me@example.com"}
        result = CliRunner().invoke(cli, ["auth", "login", "--no-browser"])
        assert result.exit_code == 0, result.output
        mock_open.assert_not_called()

    @patch("pegasus_cli.projects.webbrowser.open")
    @patch("pegasus_cli.projects.save_api_key")
    @patch("pegasus_cli.projects.wait_for_api_key")
    @patch("pegasus_cli.projects.start_device_login", return_value=START_RESPONSE)
    @patch("pegasus_cli.projects.get_api_key", return_value=None)
    def test_denied_login_exits_with_error(
        self, _get_key, mock_start, mock_wait, mock_save, mock_open
    ):
        mock_wait.side_effect = PegasusApiError("Login was denied in the browser.")
        result = CliRunner().invoke(cli, ["auth", "login"])
        assert result.exit_code == 1
        assert "denied" in result.output
        mock_save.assert_not_called()

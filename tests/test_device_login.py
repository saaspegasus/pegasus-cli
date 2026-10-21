from unittest.mock import MagicMock, patch

import pytest
import requests
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


def _response(status_code, data, headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    response.headers = headers or {}
    response.json.return_value = data
    return response


def _html_response(status_code):
    response = _response(status_code, None)
    response.json.side_effect = requests.JSONDecodeError("Expecting value", "<html>", 0)
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

    @patch("pegasus_cli.device_login.requests.post")
    def test_rate_limited_says_when_to_retry(self, mock_post):
        mock_post.return_value = _response(
            429, {"detail": "Throttled"}, {"Retry-After": "42"}
        )
        with pytest.raises(PegasusApiError, match="Try again in 42 seconds"):
            start_device_login(BASE_URL, "laptop")

    @pytest.mark.parametrize(
        "response", [_html_response(200), _response(200, {"user_code": "BCDF-GHJK"})]
    )
    @patch("pegasus_cli.device_login.requests.post")
    def test_unexpected_response(self, mock_post, response):
        mock_post.return_value = response
        with pytest.raises(PegasusApiError, match="Unexpected response"):
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

    @patch("pegasus_cli.device_login.requests.post")
    def test_rate_limit_waits_for_retry_after(self, mock_post):
        mock_post.side_effect = [
            _response(429, {"detail": "Throttled"}, {"Retry-After": "30"}),
            _response(200, {"api_key": "new-key", "email": "me@example.com"}),
        ]
        sleeps = []
        result = wait_for_api_key(BASE_URL, "code", 5, 600, sleep=sleeps.append)
        assert result["api_key"] == "new-key"
        assert sleeps == [5, 30]

    @patch("pegasus_cli.device_login.requests.post")
    def test_transient_failures_are_retried(self, mock_post):
        mock_post.side_effect = [
            requests.ConnectionError("wifi blip"),
            _html_response(502),
            _response(503, {}),
            _response(200, {"api_key": "new-key", "email": "me@example.com"}),
        ]
        result = wait_for_api_key(BASE_URL, "code", 5, 600, sleep=_no_sleep)
        assert result["api_key"] == "new-key"
        assert mock_post.call_count == 4

    @patch("pegasus_cli.device_login.requests.post")
    def test_non_json_success_is_an_error(self, mock_post):
        mock_post.return_value = _html_response(200)
        with pytest.raises(PegasusApiError, match="Unexpected response"):
            wait_for_api_key(BASE_URL, "code", 5, 600, sleep=_no_sleep)

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
    @pytest.fixture(autouse=True)
    def _environment(self, monkeypatch):
        monkeypatch.delenv("PEGASUS_API_KEY", raising=False)
        monkeypatch.setattr("pegasus_cli.projects._has_display", lambda: True)

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

    @patch("pegasus_cli.projects.webbrowser.open")
    @patch("pegasus_cli.projects.save_api_key")
    @patch("pegasus_cli.projects.wait_for_api_key")
    @patch("pegasus_cli.projects.start_device_login", return_value=START_RESPONSE)
    @patch("pegasus_cli.projects.get_api_key", return_value="stale-key")
    def test_replaces_existing_key_without_prompting(
        self, _get_key, mock_start, mock_wait, mock_save, mock_open
    ):
        mock_wait.return_value = {"api_key": "new-key", "email": "me@example.com"}
        # no input: a prompt here would abort
        result = CliRunner().invoke(cli, ["auth", "login"])
        assert result.exit_code == 0, result.output
        mock_save.assert_called_once_with("new-key")

    @patch("pegasus_cli.projects.webbrowser.open")
    @patch("pegasus_cli.projects.save_api_key")
    @patch("pegasus_cli.projects.wait_for_api_key")
    @patch("pegasus_cli.projects.start_device_login", return_value=START_RESPONSE)
    @patch("pegasus_cli.projects.get_api_key", return_value="env-key")
    def test_warns_when_env_var_overrides_saved_key(
        self, _get_key, mock_start, mock_wait, mock_save, mock_open, monkeypatch
    ):
        monkeypatch.setenv("PEGASUS_API_KEY", "env-key")
        mock_wait.return_value = {"api_key": "new-key", "email": "me@example.com"}
        result = CliRunner().invoke(cli, ["auth", "login"])
        assert result.exit_code == 0, result.output
        assert "PEGASUS_API_KEY is set" in result.output

    @pytest.mark.parametrize("has_display,opened", [(False, True), (True, False)])
    @patch("pegasus_cli.projects.webbrowser.open")
    @patch("pegasus_cli.projects.save_api_key")
    @patch("pegasus_cli.projects.wait_for_api_key")
    @patch("pegasus_cli.projects.start_device_login", return_value=START_RESPONSE)
    @patch("pegasus_cli.projects.get_api_key", return_value=None)
    def test_says_to_open_link_when_browser_cant_open(
        self,
        _get_key,
        mock_start,
        mock_wait,
        mock_save,
        mock_open,
        has_display,
        opened,
        monkeypatch,
    ):
        monkeypatch.setattr("pegasus_cli.projects._has_display", lambda: has_display)
        mock_open.return_value = opened
        mock_wait.return_value = {"api_key": "new-key", "email": "me@example.com"}
        result = CliRunner().invoke(cli, ["auth", "login"])
        assert result.exit_code == 0, result.output
        assert "open the link above yourself" in result.output
        if not has_display:
            mock_open.assert_not_called()

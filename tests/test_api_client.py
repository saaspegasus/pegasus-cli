from unittest.mock import MagicMock, patch

import pytest

from pegasus_cli.api_client import PegasusApiError, PegasusClient


@pytest.fixture
def client():
    return PegasusClient("https://example.com", "test-key")


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    return resp


class TestListProjects:
    def test_success(self, client):
        projects = [{"id": 1, "name": "Test"}]
        client.session.get = MagicMock(return_value=_mock_response(200, projects))
        result = client.list_projects()
        assert result == projects
        client.session.get.assert_called_once_with(
            "https://example.com/projects/api/projects/"
        )

    def test_auth_failure(self, client):
        client.session.get = MagicMock(return_value=_mock_response(403))
        with pytest.raises(PegasusApiError, match="Authentication failed"):
            client.list_projects()


class TestPushToGithub:
    def test_success(self, client):
        push_response = {"task_id": "abc-123", "project_id": 1}
        client.session.post = MagicMock(return_value=_mock_response(202, push_response))
        result = client.push_to_github(1)
        assert result["task_id"] == "abc-123"

    def test_with_upgrade(self, client):
        client.session.post = MagicMock(return_value=_mock_response(202, {}))
        client.push_to_github(1, upgrade_to_latest=True)
        call_kwargs = client.session.post.call_args
        assert call_kwargs.kwargs["json"] == {"upgrade_to_latest": True}

    def test_with_upgrade_dev_channel(self, client):
        client.session.post = MagicMock(return_value=_mock_response(202, {}))
        client.push_to_github(1, upgrade_to_latest=True, release_channel="dev")
        call_kwargs = client.session.post.call_args
        assert call_kwargs.kwargs["json"] == {
            "upgrade_to_latest": True,
            "release_channel": "dev",
        }

    def test_stable_channel_not_sent(self, client):
        client.session.post = MagicMock(return_value=_mock_response(202, {}))
        client.push_to_github(1, upgrade_to_latest=True, release_channel="stable")
        call_kwargs = client.session.post.call_args
        assert call_kwargs.kwargs["json"] == {"upgrade_to_latest": True}

    def test_bad_request(self, client):
        error_resp = _mock_response(400, {"error": "No GitHub repository configured."})
        client.session.post = MagicMock(return_value=error_resp)
        with pytest.raises(PegasusApiError, match="No GitHub repository"):
            client.push_to_github(1)

    def test_not_found(self, client):
        client.session.post = MagicMock(return_value=_mock_response(404))
        with pytest.raises(PegasusApiError, match="not found"):
            client.push_to_github(1)


class TestGetTaskStatus:
    def test_success(self, client):
        status = {"state": "PROGRESS", "complete": False}
        client.session.get = MagicMock(return_value=_mock_response(200, status))
        result = client.get_task_status(1, "abc-123")
        assert result["state"] == "PROGRESS"
        client.session.get.assert_called_once_with(
            "https://example.com/projects/api/1/tasks/abc-123/"
        )


class TestPollTask:
    def test_polls_until_complete(self, client):
        in_progress = {
            "state": "PROGRESS",
            "complete": False,
            "progress": {"percent": 50},
        }
        done = {"state": "SUCCESS", "complete": True, "success": True}
        client.session.get = MagicMock(
            side_effect=[_mock_response(200, in_progress), _mock_response(200, done)]
        )
        with patch("pegasus_cli.api_client.time.sleep"):
            statuses = list(client.poll_task(1, "abc-123"))
        assert len(statuses) == 2
        assert statuses[-1]["complete"] is True


class TestAuthHeader:
    def test_api_key_header(self, client):
        assert client.session.headers["Authorization"] == "Api-Key test-key"

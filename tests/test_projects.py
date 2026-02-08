from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pegasus_cli.cli import cli


def _mock_client(projects=None, push_response=None, poll_statuses=None):
    """Create a mock PegasusClient."""
    client = MagicMock()
    client.list_projects.return_value = projects or []
    client.push_to_github.return_value = push_response or {
        "task_id": "abc-123",
        "project_id": 1,
        "pegasus_version": "2025.1",
    }

    if poll_statuses:
        client.poll_task.return_value = iter(poll_statuses)
    else:
        client.poll_task.return_value = iter(
            [
                {
                    "state": "SUCCESS",
                    "complete": True,
                    "success": True,
                    "result": {
                        "pull_request_url": "https://github.com/user/repo/pull/1"
                    },
                }
            ]
        )
    return client


class TestAuth:
    @patch("pegasus_cli.projects.PegasusClient")
    @patch("pegasus_cli.projects.get_api_key", return_value=None)
    def test_auth_saves_key(self, mock_get_key, mock_client_cls):
        mock_client_cls.return_value.list_projects.return_value = []
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch("pegasus_cli.projects.save_api_key") as mock_save:
                mock_save.return_value = "/home/user/.pegasus/credentials"
                result = runner.invoke(cli, ["auth"], input="my-api-key\n")
                assert result.exit_code == 0
                mock_save.assert_called_once_with("my-api-key")

    @patch("pegasus_cli.projects.PegasusClient")
    @patch("pegasus_cli.projects.get_api_key", return_value="existing-key")
    def test_auth_prompts_to_replace(self, mock_get_key, mock_client_cls):
        runner = CliRunner()
        result = runner.invoke(cli, ["auth"], input="n\n")
        assert result.exit_code == 0
        assert "already configured" in result.output


class TestProjectsList:
    @patch("pegasus_cli.projects._get_client")
    def test_list_shows_projects(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            projects=[
                {
                    "id": 1,
                    "name": "My App",
                    "pegasus_version": "2025.1",
                    "has_github_repo": True,
                    "has_valid_license": True,
                },
            ]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "list"])
        assert result.exit_code == 0
        assert "My App" in result.output
        assert "v2025.1" in result.output
        assert "\u2705 licensed" in result.output
        assert "\u2705 github" in result.output

    @patch("pegasus_cli.projects._get_client")
    def test_list_shows_latest_version(self, mock_get_client):
        mock_get_client.return_value = _mock_client(
            projects=[
                {
                    "id": 1,
                    "name": "My App",
                    "pegasus_version": "2025.1",
                    "has_github_repo": True,
                    "has_valid_license": True,
                    "use_latest_version": True,
                },
            ]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "list"])
        assert result.exit_code == 0
        assert "v2025.1 (latest)" in result.output

    @patch("pegasus_cli.projects._get_client")
    def test_list_empty(self, mock_get_client):
        mock_get_client.return_value = _mock_client(projects=[])
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "list"])
        assert result.exit_code == 0
        assert "No projects found" in result.output


class TestProjectsPush:
    @patch("pegasus_cli.projects._get_client")
    def test_push_with_id(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "42"])
        assert result.exit_code == 0
        assert "Pull request created" in result.output
        client.push_to_github.assert_called_once_with(
            42, upgrade_to_latest=False, release_channel="stable"
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_with_upgrade(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "42", "--upgrade"])
        assert result.exit_code == 0
        client.push_to_github.assert_called_once_with(
            42, upgrade_to_latest=True, release_channel="stable"
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_with_dev_flag(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "42", "--upgrade", "--dev"])
        assert result.exit_code == 0
        client.push_to_github.assert_called_once_with(
            42, upgrade_to_latest=True, release_channel="dev"
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_interactive_selection(self, mock_get_client):
        client = _mock_client(
            projects=[
                {
                    "id": 10,
                    "name": "First",
                    "pegasus_version": "2025.1",
                    "has_github_repo": True,
                },
                {
                    "id": 20,
                    "name": "Second",
                    "pegasus_version": "2025.1",
                    "has_github_repo": True,
                },
            ]
        )
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push"], input="2\n")
        assert result.exit_code == 0
        client.push_to_github.assert_called_once_with(
            20, upgrade_to_latest=False, release_channel="stable"
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_shows_progress(self, mock_get_client):
        client = _mock_client(
            poll_statuses=[
                {
                    "state": "PROGRESS",
                    "complete": False,
                    "progress": {"percent": 10, "description": "creating codebase..."},
                },
                {
                    "state": "PROGRESS",
                    "complete": False,
                    "progress": {"percent": 60, "description": "building front end..."},
                },
                {
                    "state": "SUCCESS",
                    "complete": True,
                    "success": True,
                    "result": {
                        "pull_request_url": "https://github.com/user/repo/pull/1"
                    },
                },
            ]
        )
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "1"])
        assert result.exit_code == 0
        assert "creating codebase" in result.output
        assert "building front end" in result.output

    @patch("pegasus_cli.projects._get_client")
    def test_push_failure(self, mock_get_client):
        client = _mock_client(
            poll_statuses=[
                {
                    "state": "FAILURE",
                    "complete": True,
                    "success": False,
                    "result": "No GitHub token found.",
                },
            ]
        )
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "1"])
        assert result.exit_code != 0
        assert "No GitHub token found" in result.output

    @patch("pegasus_cli.projects._get_client")
    def test_push_repo_url_on_first_push(self, mock_get_client):
        client = _mock_client(
            poll_statuses=[
                {
                    "state": "SUCCESS",
                    "complete": True,
                    "success": True,
                    "result": {"repo_url": "https://github.com/user/repo/"},
                },
            ]
        )
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "1"])
        assert result.exit_code == 0
        assert "Repository created" in result.output

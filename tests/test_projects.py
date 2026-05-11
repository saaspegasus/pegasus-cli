import json
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
        assert "2025.1" in result.output
        assert "\u2705" in result.output

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
        assert "2025.1 (latest)" in result.output

    @patch("pegasus_cli.projects._get_client")
    def test_list_empty(self, mock_get_client):
        mock_get_client.return_value = _mock_client(projects=[])
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "list"])
        assert result.exit_code == 0
        assert "No projects found" in result.output


class TestProjectsPush:
    @patch("pegasus_cli.projects._get_client")
    def test_push_no_upgrade(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "42"], input="3\n")
        assert result.exit_code == 0
        assert "Pull request created" in result.output
        client.push_to_github.assert_called_once_with(
            42, upgrade_to_latest=False, release_channel="stable", pr_title=None
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_prompts_upgrade_stable(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "42"], input="1\n")
        assert result.exit_code == 0
        assert "Upgrade options" in result.output
        client.push_to_github.assert_called_once_with(
            42, upgrade_to_latest=True, release_channel="stable", pr_title=None
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_prompts_upgrade_dev(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "42"], input="2\n")
        assert result.exit_code == 0
        client.push_to_github.assert_called_once_with(
            42, upgrade_to_latest=True, release_channel="dev", pr_title=None
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_with_upgrade(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "42", "--upgrade"])
        assert result.exit_code == 0
        client.push_to_github.assert_called_once_with(
            42, upgrade_to_latest=True, release_channel="stable", pr_title=None
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_dev_implies_upgrade(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "push", "42", "--dev"])
        assert result.exit_code == 0
        client.push_to_github.assert_called_once_with(
            42, upgrade_to_latest=True, release_channel="dev", pr_title=None
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
        result = runner.invoke(cli, ["projects", "push"], input="2\n3\n")
        assert result.exit_code == 0
        client.push_to_github.assert_called_once_with(
            20, upgrade_to_latest=False, release_channel="stable", pr_title=None
        )

    @patch("pegasus_cli.projects._get_client")
    def test_push_with_pr_title(self, mock_get_client):
        client = _mock_client()
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "projects",
                "push",
                "42",
                "--upgrade",
                "--pr-title",
                "Upgrade Pegasus to 2025.2",
            ],
        )
        assert result.exit_code == 0
        client.push_to_github.assert_called_once_with(
            42,
            upgrade_to_latest=True,
            release_channel="stable",
            pr_title="Upgrade Pegasus to 2025.2",
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
        result = runner.invoke(cli, ["projects", "push", "1"], input="3\n")
        assert result.exit_code == 0
        # Rich progress bar renders description text in output
        assert (
            "creating codebase" in result.output
            or "Pull request created" in result.output
        )
        assert "Pull request created" in result.output

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
        result = runner.invoke(cli, ["projects", "push", "1"], input="3\n")
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
        result = runner.invoke(cli, ["projects", "push", "1"], input="3\n")
        assert result.exit_code == 0
        assert "Repository created" in result.output


class TestProjectsShow:
    @patch("pegasus_cli.projects._get_client")
    def test_show_table(self, mock_get_client):
        client = MagicMock()
        client.get_project.return_value = {
            "id": 42,
            "project_name": "My App",
            "project_slug": "my_app",
            "use_celery": True,
        }
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "show", "42"])
        assert result.exit_code == 0
        assert "My App" in result.output
        assert "project_slug" in result.output
        client.get_project.assert_called_once_with(42)

    @patch("pegasus_cli.projects._get_client")
    def test_show_json(self, mock_get_client):
        client = MagicMock()
        config = {"id": 42, "project_name": "My App", "use_celery": True}
        client.get_project.return_value = config
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "show", "42", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed == config


class TestProjectsFields:
    @patch("pegasus_cli.projects._get_client")
    def test_fields_table(self, mock_get_client):
        client = MagicMock()
        client.get_schema.return_value = {
            "fields": {
                "project_name": {"type": "string", "read_only": False},
                "use_celery": {"type": "boolean", "read_only": False},
                "front_end_framework": {
                    "type": "choice",
                    "read_only": False,
                    "choices": ["htmx", "react"],
                },
            }
        }
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "fields"])
        assert result.exit_code == 0
        assert "project_name" in result.output
        assert "boolean" in result.output
        assert "htmx" in result.output

    @patch("pegasus_cli.projects._get_client")
    def test_fields_json(self, mock_get_client):
        client = MagicMock()
        schema = {"fields": {"project_name": {"type": "string"}}}
        client.get_schema.return_value = schema
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "fields", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output) == schema

    @patch("pegasus_cli.projects._get_client")
    def test_fields_table_shows_user_tier_and_min_tier(self, mock_get_client):
        client = MagicMock()
        client.get_schema.return_value = {
            "user_tier": "pro",
            "fields": {
                "project_name": {"type": "string", "read_only": False},
                "use_celery": {
                    "type": "boolean",
                    "read_only": False,
                    "min_tier": "free",
                },
                "use_subscriptions": {
                    "type": "boolean",
                    "read_only": False,
                    "min_tier": "pro",
                },
            },
        }
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "fields"])
        assert result.exit_code == 0
        # user_tier surfaced in the table title
        assert "your tier: pro" in result.output
        # Min Tier column rendered with values for gated features
        assert "Min Tier" in result.output
        assert "free" in result.output
        assert "pro" in result.output


class TestProjectsCreate:
    @patch("pegasus_cli.projects._get_client")
    def test_create_with_set_pairs(self, mock_get_client):
        client = MagicMock()
        client.create_project.return_value = {
            "id": 1,
            "project_name": "My App",
            "project_slug": "my_app",
        }
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "projects",
                "create",
                "--set",
                "project_name=My App",
                "--set",
                "project_slug=my_app",
                "--set",
                "use_celery=true",
                "--set",
                "ai_chat_mode=llm",
            ],
        )
        assert result.exit_code == 0, result.output
        client.create_project.assert_called_once_with(
            {
                "project_name": "My App",
                "project_slug": "my_app",
                "use_celery": True,
                "ai_chat_mode": "llm",
            }
        )

    @patch("pegasus_cli.projects._get_client")
    def test_create_with_config_file_yaml(self, mock_get_client):
        client = MagicMock()
        client.create_project.return_value = {
            "id": 1,
            "project_name": "From File",
            "project_slug": "from_file",
        }
        mock_get_client.return_value = client
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("config.yaml", "w") as f:
                f.write(
                    "project_name: From File\nproject_slug: from_file\nuse_celery: true\n"
                )
            result = runner.invoke(
                cli, ["projects", "create", "--config-file", "config.yaml"]
            )
        assert result.exit_code == 0, result.output
        client.create_project.assert_called_once_with(
            {
                "project_name": "From File",
                "project_slug": "from_file",
                "use_celery": True,
            }
        )

    @patch("pegasus_cli.projects._get_client")
    def test_create_with_default_context_yaml(self, mock_get_client):
        """A real pegasus-config.yaml has a `default_context` wrapper key; we unwrap it."""
        client = MagicMock()
        client.create_project.return_value = {"id": 1}
        mock_get_client.return_value = client
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("pegasus-config.yaml", "w") as f:
                f.write(
                    "default_context:\n  project_name: Wrapped\n  project_slug: wrapped\n"
                )
            result = runner.invoke(
                cli, ["projects", "create", "--config-file", "pegasus-config.yaml"]
            )
        assert result.exit_code == 0, result.output
        client.create_project.assert_called_once_with(
            {"project_name": "Wrapped", "project_slug": "wrapped"}
        )

    @patch("pegasus_cli.projects._get_client")
    def test_create_set_overrides_config_file(self, mock_get_client):
        client = MagicMock()
        client.create_project.return_value = {"id": 1}
        mock_get_client.return_value = client
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("config.yaml", "w") as f:
                f.write(
                    "project_name: From File\nproject_slug: from_file\nuse_celery: false\n"
                )
            result = runner.invoke(
                cli,
                [
                    "projects",
                    "create",
                    "--config-file",
                    "config.yaml",
                    "--set",
                    "use_celery=true",
                ],
            )
        assert result.exit_code == 0, result.output
        call_kwargs = client.create_project.call_args
        # --set overrides config-file
        assert call_kwargs.args[0]["use_celery"] is True
        assert call_kwargs.args[0]["project_slug"] == "from_file"

    def test_create_no_input_errors(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "create"])
        assert result.exit_code != 0
        assert "Nothing to do" in result.output

    def test_create_bad_set_format_errors(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "create", "--set", "no_equals_sign"])
        assert result.exit_code != 0
        assert "key=value" in result.output

    @patch("pegasus_cli.projects._get_client")
    def test_create_set_value_null(self, mock_get_client):
        client = MagicMock()
        client.create_project.return_value = {"id": 1}
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "projects",
                "create",
                "--set",
                "project_name=Foo",
                "--set",
                "project_slug=foo",
                "--set",
                "pegasus_version=null",
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = client.create_project.call_args
        assert call_kwargs.args[0]["pegasus_version"] is None


class TestProjectsUpdate:
    @patch("pegasus_cli.projects._get_client")
    def test_update_with_set_pairs(self, mock_get_client):
        client = MagicMock()
        client.update_project.return_value = {"id": 42, "project_name": "Updated"}
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "projects",
                "update",
                "42",
                "--set",
                "use_celery=true",
                "--set",
                "ai_chat_mode=llm",
            ],
        )
        assert result.exit_code == 0, result.output
        client.update_project.assert_called_once_with(
            42, {"use_celery": True, "ai_chat_mode": "llm"}
        )

    @patch("pegasus_cli.projects._get_client")
    def test_update_with_config_file(self, mock_get_client):
        client = MagicMock()
        client.update_project.return_value = {"id": 42}
        mock_get_client.return_value = client
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("config.json", "w") as f:
                f.write('{"use_celery": true, "ai_chat_mode": "llm"}')
            result = runner.invoke(
                cli, ["projects", "update", "42", "--config-file", "config.json"]
            )
        assert result.exit_code == 0, result.output
        client.update_project.assert_called_once_with(
            42, {"use_celery": True, "ai_chat_mode": "llm"}
        )

    def test_update_no_input_errors(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["projects", "update", "42"])
        assert result.exit_code != 0
        assert "Nothing to update" in result.output

    @patch("pegasus_cli.projects._get_client")
    def test_update_json_output(self, mock_get_client):
        client = MagicMock()
        config = {"id": 42, "project_name": "Updated"}
        client.update_project.return_value = config
        mock_get_client.return_value = client
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["projects", "update", "42", "--set", "project_name=Updated", "--json"],
        )
        assert result.exit_code == 0
        assert json.loads(result.output) == config

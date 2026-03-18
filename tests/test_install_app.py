import pathlib
import textwrap

from pegasus_cli.startapp import (
    add_to_installed_apps,
    add_to_urlpatterns,
    find_settings_from_manage_py,
)

APP_CONFIG = "myapp.apps.MyappConfig"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_settings(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    settings = tmp_path / "settings.py"
    settings.write_text(textwrap.dedent(content))
    return settings


def installed_apps_contents(settings: pathlib.Path) -> list[str]:
    """Evaluate the settings file and return the INSTALLED_APPS list."""
    ns: dict = {}
    exec(settings.read_text(), ns)
    return ns["INSTALLED_APPS"]


# ---------------------------------------------------------------------------
# Direct INSTALLED_APPS list
# ---------------------------------------------------------------------------


def test_installed_apps_multiline(tmp_path):
    settings = write_settings(
        tmp_path,
        """
        INSTALLED_APPS = [
            "django.contrib.auth",
            "django.contrib.contenttypes",
        ]
    """,
    )

    result = add_to_installed_apps(str(settings), APP_CONFIG)

    assert result is True
    assert APP_CONFIG in settings.read_text()
    apps = installed_apps_contents(settings)
    assert apps[-1] == APP_CONFIG


def test_installed_apps_single_line(tmp_path):
    settings = write_settings(
        tmp_path,
        """
        INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes"]
    """,
    )

    result = add_to_installed_apps(str(settings), APP_CONFIG)

    assert result is True
    apps = installed_apps_contents(settings)
    assert APP_CONFIG in apps


def test_installed_apps_empty_list(tmp_path):
    settings = write_settings(
        tmp_path,
        """
        INSTALLED_APPS = []
    """,
    )

    result = add_to_installed_apps(str(settings), APP_CONFIG)

    assert result is True
    apps = installed_apps_contents(settings)
    assert apps == [APP_CONFIG]


# ---------------------------------------------------------------------------
# PROJECT_APPS pattern (Pegasus style)
# ---------------------------------------------------------------------------


def test_project_apps_multiline(tmp_path):
    """PROJECT_APPS is preferred over INSTALLED_APPS when both are present."""
    settings = write_settings(
        tmp_path,
        """
        DJANGO_APPS = [
            "django.contrib.auth",
            "django.contrib.contenttypes",
        ]

        PROJECT_APPS = [
            "apps.users",
        ]

        INSTALLED_APPS = DJANGO_APPS + PROJECT_APPS
    """,
    )

    result = add_to_installed_apps(str(settings), APP_CONFIG)

    assert result is True
    text = settings.read_text()
    assert APP_CONFIG in text

    # The entry must be inside PROJECT_APPS, not DJANGO_APPS
    project_block_start = text.index("PROJECT_APPS")
    installed_block_start = text.index("INSTALLED_APPS")
    entry_pos = text.index(APP_CONFIG)
    assert project_block_start < entry_pos < installed_block_start


def test_project_apps_only(tmp_path):
    settings = write_settings(
        tmp_path,
        """
        DJANGO_APPS = [
            "django.contrib.auth",
        ]

        PROJECT_APPS = [
            "apps.users",
        ]

        INSTALLED_APPS = DJANGO_APPS + PROJECT_APPS
    """,
    )

    result = add_to_installed_apps(str(settings), APP_CONFIG)

    assert result is True
    # Evaluate combined INSTALLED_APPS to confirm the entry is reachable
    ns: dict = {}
    exec(settings.read_text(), ns)
    assert APP_CONFIG in ns["INSTALLED_APPS"]


# ---------------------------------------------------------------------------
# Edge / failure cases
# ---------------------------------------------------------------------------


def test_no_installed_apps_returns_false(tmp_path):
    settings = write_settings(
        tmp_path,
        """
        DEBUG = True
        DATABASES = {}
    """,
    )

    result = add_to_installed_apps(str(settings), APP_CONFIG)

    assert result is False
    assert APP_CONFIG not in settings.read_text()


def test_file_not_modified_when_no_list_found(tmp_path):
    content = textwrap.dedent(
        """
        DEBUG = True
    """
    )
    settings = write_settings(tmp_path, content)
    original = settings.read_text()

    add_to_installed_apps(str(settings), APP_CONFIG)

    assert settings.read_text() == original


def test_other_file_content_preserved(tmp_path):
    settings = write_settings(
        tmp_path,
        """
        SECRET_KEY = "abc123"

        INSTALLED_APPS = [
            "django.contrib.auth",
        ]

        DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3"}}
    """,
    )

    add_to_installed_apps(str(settings), APP_CONFIG)

    text = settings.read_text()
    assert "SECRET_KEY" in text
    assert "DATABASES" in text


# ---------------------------------------------------------------------------
# find_settings_from_manage_py
# ---------------------------------------------------------------------------


def write_manage_py(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    manage = tmp_path / "manage.py"
    manage.write_text(textwrap.dedent(content))
    return manage


def make_settings_file(tmp_path: pathlib.Path, module: str) -> pathlib.Path:
    """Create an empty settings file at the location implied by the module name."""
    rel = pathlib.Path(module.replace(".", "/")).with_suffix(".py")
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# settings\n")
    return path


def test_find_settings_setdefault(tmp_path):
    make_settings_file(tmp_path, "myproject.settings")
    manage = write_manage_py(
        tmp_path,
        """
        import os
        import sys

        def main():
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

        if __name__ == "__main__":
            main()
    """,
    )

    result = find_settings_from_manage_py(manage)

    assert result is not None
    assert result == tmp_path / "myproject" / "settings.py"


def test_find_settings_direct_assignment(tmp_path):
    make_settings_file(tmp_path, "myproject.settings.local")
    manage = write_manage_py(
        tmp_path,
        """
        import os
        os.environ["DJANGO_SETTINGS_MODULE"] = "myproject.settings.local"
    """,
    )

    result = find_settings_from_manage_py(manage)

    assert result is not None
    assert result == tmp_path / "myproject" / "settings" / "local.py"


def test_find_settings_returns_none_when_not_set(tmp_path):
    manage = write_manage_py(
        tmp_path,
        """
        import os
        def main():
            pass
    """,
    )

    assert find_settings_from_manage_py(manage) is None


def test_find_settings_returns_none_when_file_missing(tmp_path):
    """Module name found in manage.py but settings file doesn't exist on disk."""
    manage = write_manage_py(
        tmp_path,
        """
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nonexistent.settings")
    """,
    )

    assert find_settings_from_manage_py(manage) is None


def test_find_settings_returns_none_for_missing_manage_py(tmp_path):
    assert find_settings_from_manage_py(tmp_path / "manage.py") is None


# ---------------------------------------------------------------------------
# add_to_urlpatterns
# ---------------------------------------------------------------------------


def write_urls(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    urls = tmp_path / "urls.py"
    urls.write_text(textwrap.dedent(content))
    return urls


def test_urlpatterns_multiline(tmp_path):
    urls = write_urls(
        tmp_path,
        """
        from django.urls import path, include

        urlpatterns = [
            path("admin/", admin.site.urls),
        ]
    """,
    )

    result = add_to_urlpatterns(str(urls), "golf", "apps.golf", use_teams=False)

    assert result is True
    text = urls.read_text()
    assert 'path("golf/", include("apps.golf.urls"))' in text
    # Verify existing entry is preserved
    assert 'path("admin/", admin.site.urls)' in text


def test_urlpatterns_empty_list(tmp_path):
    urls = write_urls(
        tmp_path,
        """
        from django.urls import path

        urlpatterns = []
    """,
    )

    result = add_to_urlpatterns(str(urls), "golf", "apps.golf", use_teams=False)

    assert result is True
    assert 'path("golf/", include("apps.golf.urls"))' in urls.read_text()


def test_team_urlpatterns(tmp_path):
    urls = write_urls(
        tmp_path,
        """
        from django.urls import path, include

        team_urlpatterns = [
            path("dashboard/", views.dashboard),
        ]
    """,
    )

    result = add_to_urlpatterns(str(urls), "golf", "apps.golf", use_teams=True)

    assert result is True
    text = urls.read_text()
    assert 'path("golf/", include("apps.golf.urls"))' in text
    # Entry must be inside team_urlpatterns block
    team_block_start = text.index("team_urlpatterns")
    entry_pos = text.index('path("golf/"')
    assert entry_pos > team_block_start


def test_urlpatterns_not_found_returns_false(tmp_path):
    urls = write_urls(
        tmp_path,
        """
        # empty urls file
        from django.urls import path
    """,
    )

    result = add_to_urlpatterns(str(urls), "golf", "apps.golf", use_teams=False)

    assert result is False


def test_use_teams_false_ignores_team_urlpatterns(tmp_path):
    """With use_teams=False, only urlpatterns is targeted, not team_urlpatterns."""
    urls = write_urls(
        tmp_path,
        """
        from django.urls import path, include

        team_urlpatterns = [
            path("dashboard/", views.dashboard),
        ]
    """,
    )

    result = add_to_urlpatterns(str(urls), "golf", "apps.golf", use_teams=False)

    assert result is False

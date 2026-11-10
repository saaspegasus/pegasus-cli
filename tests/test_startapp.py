import json
import pathlib

import click
import pytest

from pegasus_cli.startapp import _check_htmx_version, _get_htmx_major_version


def test_htmx_4_passes(tmp_path):
    package_json = write_package_json(
        tmp_path, {"dependencies": {"htmx.org": "^4.0.1"}}
    )
    _check_htmx_version(package_json)


def test_htmx_2_fails(tmp_path):
    package_json = write_package_json(
        tmp_path, {"dependencies": {"htmx.org": "^2.0.4"}}
    )
    with pytest.raises(click.ClickException, match="--force"):
        _check_htmx_version(package_json)


@pytest.mark.parametrize(
    "spec, expected",
    [
        ("^4.0.1", 4),
        ("~2.0.8", 2),
        ("2.0.4", 2),
        (">=4.0.0", 4),
        ("4.0.0-beta3", 4),
        ("latest", None),
    ],
)
def test_version_specs(tmp_path, spec, expected):
    package_json = write_package_json(tmp_path, {"dependencies": {"htmx.org": spec}})
    assert _get_htmx_major_version(package_json) == expected


def test_dev_dependency(tmp_path):
    package_json = write_package_json(
        tmp_path, {"devDependencies": {"htmx.org": "^2.0.4"}}
    )
    assert _get_htmx_major_version(package_json) == 2


def test_unknown_version_passes(tmp_path):
    # missing file, invalid json, and no htmx dependency should all be let through
    _check_htmx_version(tmp_path / "package.json")
    (tmp_path / "package.json").write_text("not json")
    _check_htmx_version(tmp_path / "package.json")
    _check_htmx_version(
        write_package_json(tmp_path, {"dependencies": {"alpinejs": "^3.0.0"}})
    )


def write_package_json(tmp_path: pathlib.Path, data: dict) -> pathlib.Path:
    package_json = tmp_path / "package.json"
    package_json.write_text(json.dumps(data))
    return package_json

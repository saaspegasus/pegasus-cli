# cli

[![PyPI](https://img.shields.io/pypi/v/cli.svg)](https://pypi.org/project/cli/)
[![Changelog](https://img.shields.io/github/v/release/saaspegasus/cli?include_prereleases&label=changelog)](https://github.com/saaspegasus/cli/releases)
[![Tests](https://github.com/saaspegasus/cli/actions/workflows/test.yml/badge.svg)](https://github.com/saaspegasus/cli/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/saaspegasus/cli/blob/master/LICENSE)

null

## Installation

Install this tool using `pip`:
```bash
pip install pegasus-cli
```
## Usage

For help, run:
```bash
pegasus --help
```
You can also use:
```bash
python -m pegasus --help
```
## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment:
```bash
cd cli
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and dev dependencies:
```bash
pip install -e '.[dev]'
```
To run the tests:
```bash
pytest
```
Setup pre-commit hooks:
```bash
pre-commit install
```

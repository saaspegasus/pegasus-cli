# cli

[![PyPI](https://img.shields.io/pypi/v/cli.svg)](https://pypi.org/project/cli/)
[![Changelog](https://img.shields.io/github/v/release/saaspegasus/cli?include_prereleases&label=changelog)](https://github.com/saaspegasus/cli/releases)
[![Tests](https://github.com/saaspegasus/cli/actions/workflows/test.yml/badge.svg)](https://github.com/saaspegasus/cli/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/saaspegasus/cli/blob/master/LICENSE)


## Demo

A demo is worth 1,000 words. Click the image below to see the Pegasus CLI in action:

[![Pegasus CLI Demo](https://img.youtube.com/vi/wKS_bbD5RVs/0.jpg)](https://www.youtube.com/watch?v=wKS_bbD5RVs)

## Overview

The Pegasus CLI is a command-line tool that streamlines the process of working in a Django project.
It is currently designed to work with the [SaaS Pegasus Django boilerplate](https://www.saaspegasus.com/),
but can be used more generally for any Django project (and will be updated to work with generic
Django projects in the future).

It is currently geared around the `startapp` command. This will create a new app in your Django project,
and (optionally) spin up an entire Create / Update / Delete (CRUD) interface for it, built with
Django forms and HTMX.

Example usage:

```bash
pegasus startapp todos Project Todo
```

This will create a `todos` app in your Django project with models, URLs, views and templates to
work with a `Project` and `Todo` model.

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
## Configuration

You can run `pegasus startapp --help` for configuration options.
In addition to the command-line options, you can also set default values for configuration
options by creating a `pegasus-config.yaml` file in your project directory.
The format of the file is:

```yaml
cli:
  app_directory: apps
  module_path: apps
  template_directory: templates
```

The above configuration is the recommended configuration for SaaS Pegasus projects,
and will be included in your project's `pegasus-config.yaml` file if you are on Pegasus
version 2024.9 or later.

It will create your apps in the `apps` directory, and will use the `templates` directory
for your templates.

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

import logging
import subprocess

logger = logging.getLogger("pegasus")


def run_ruff_format(path):
    """Run 'ruff format' on the given path."""
    if not _ruff_exists():
        return

    command = ["ruff", "format"] + [path]
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as e:
        logger.warning("Ruff command failed with error: %s", e)


def _ruff_exists():
    """Check if ruff is installed and available in the system path."""
    try:
        subprocess.check_call(["ruff", "--version"])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

"""Browser-based login, using the server's device authorization flow (RFC 8628)."""

import time
from collections.abc import Callable

import requests

from .api_client import PegasusApiError


def start_device_login(base_url: str, client_name: str) -> dict:
    """Start a login. Returns the device code, user code, and verification URLs from the server."""
    response = requests.post(
        f"{base_url}/cli-auth/api/start/",
        json={"client_name": client_name[:100]},
        timeout=30,
    )
    if response.status_code == 404:
        raise PegasusApiError(
            "This server doesn't support browser login. "
            "Use 'pegasus auth login --with-key' instead.",
            response.status_code,
        )
    if not response.ok:
        raise PegasusApiError(
            f"Could not start login (HTTP {response.status_code}).",
            response.status_code,
        )
    return response.json()


def wait_for_api_key(
    base_url: str,
    device_code: str,
    interval: float,
    expires_in: float,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Poll until the user approves the login. Returns {"api_key", "email"}."""
    deadline = time.monotonic() + expires_in
    while time.monotonic() < deadline:
        sleep(interval)
        response = requests.post(
            f"{base_url}/cli-auth/api/token/",
            json={"device_code": device_code},
            timeout=30,
        )
        if response.ok:
            return response.json()
        error = _error_code(response)
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error == "access_denied":
            raise PegasusApiError("Login was denied in the browser.")
        if error in ("expired_token", "invalid_grant"):
            raise PegasusApiError("Login expired. Run 'pegasus auth login' again.")
        raise PegasusApiError(
            f"Unexpected error while waiting for login (HTTP {response.status_code}).",
            response.status_code,
        )
    raise PegasusApiError("Login expired. Run 'pegasus auth login' again.")


def _error_code(response: requests.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        return None
    return data.get("error") if isinstance(data, dict) else None

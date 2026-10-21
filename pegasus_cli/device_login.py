"""Browser-based login, using the server's device authorization flow (RFC 8628)."""

import time
from collections.abc import Callable

import requests

from .api_client import PegasusApiError

START_FIELDS = (
    "device_code",
    "user_code",
    "verification_uri_complete",
    "interval",
    "expires_in",
)


def start_device_login(base_url: str, client_name: str) -> dict:
    """Start a login. Returns the device code, user code, and verification URLs from the server."""
    url = f"{base_url}/cli-auth/api/start/"
    response = requests.post(url, json={"client_name": client_name[:100]}, timeout=30)
    if response.status_code == 404:
        raise PegasusApiError(
            "This server doesn't support browser login. "
            "Use 'pegasus auth login --with-key' instead.",
            response.status_code,
        )
    if response.status_code == 429:
        raise PegasusApiError(
            "Too many login attempts right now. "
            f"Try again in {_retry_after(response, 60)} seconds, "
            "or use 'pegasus auth login --with-key'.",
            response.status_code,
        )
    if not response.ok:
        raise PegasusApiError(
            f"Could not start login (HTTP {response.status_code}).",
            response.status_code,
        )
    data = _json(response)
    if not isinstance(data, dict) or not all(field in data for field in START_FIELDS):
        raise _unexpected_response(url)
    return data


def wait_for_api_key(
    base_url: str,
    device_code: str,
    interval: float,
    expires_in: float,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Poll until the user approves the login. Returns {"api_key", "email"}.

    Connection errors, server errors and rate limits are retried until the login expires,
    since the user may take several minutes to sign up and approve it.
    """
    url = f"{base_url}/cli-auth/api/token/"
    deadline = time.monotonic() + expires_in
    retry_after = None
    while time.monotonic() < deadline:
        sleep(retry_after or interval)
        retry_after = None
        try:
            response = requests.post(url, json={"device_code": device_code}, timeout=30)
        except requests.RequestException:
            # e.g. a wifi blip or the server restarting during a deploy
            continue
        if response.status_code == 429:
            retry_after = _retry_after(response, interval)
            continue
        if response.status_code >= 500:
            continue
        data = _json(response)
        if response.ok:
            if (
                not isinstance(data, dict)
                or "api_key" not in data
                or "email" not in data
            ):
                raise _unexpected_response(url)
            return data
        error = data.get("error") if isinstance(data, dict) else None
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


def _json(response: requests.Response):
    try:
        return response.json()
    except ValueError:
        return None


def _retry_after(response: requests.Response, default: float) -> int:
    try:
        return max(int(float(response.headers.get("Retry-After", default))), 1)
    except ValueError:
        return int(default)


def _unexpected_response(url: str) -> PegasusApiError:
    return PegasusApiError(
        f"Unexpected response from {url}. Check that the server URL is right."
    )

import time

import requests


class PegasusApiError(Exception):
    """Raised when the Pegasus API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class PegasusClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Api-Key {api_key}"

    def _url(self, path: str) -> str:
        return f"{self.base_url}/projects/api/{path.lstrip('/')}"

    def _handle_error(self, response: requests.Response) -> None:
        if response.status_code == 403:
            raise PegasusApiError(
                "Authentication failed. Check your API key.", response.status_code
            )
        if response.status_code == 404:
            raise PegasusApiError(
                "Project not found or you don't have access.", response.status_code
            )
        if response.status_code == 400:
            data = response.json()
            raise PegasusApiError(
                data.get("error", "Bad request."), response.status_code
            )
        if not response.ok:
            raise PegasusApiError(
                f"Unexpected error (HTTP {response.status_code}).", response.status_code
            )

    def list_projects(self) -> list[dict]:
        response = self.session.get(self._url("projects/"))
        self._handle_error(response)
        return response.json()

    def push_to_github(self, project_id: int, upgrade_to_latest: bool = False) -> dict:
        payload = {}
        if upgrade_to_latest:
            payload["upgrade_to_latest"] = True
        response = self.session.post(
            self._url(f"{project_id}/push-to-github/"),
            json=payload,
        )
        self._handle_error(response)
        return response.json()

    def get_task_status(self, project_id: int, task_id: str) -> dict:
        response = self.session.get(self._url(f"{project_id}/tasks/{task_id}/"))
        self._handle_error(response)
        return response.json()

    def poll_task(self, project_id: int, task_id: str, poll_interval: float = 3.0):
        """Poll a task until completion, yielding status dicts along the way."""
        while True:
            status = self.get_task_status(project_id, task_id)
            yield status
            if status.get("complete"):
                return
            time.sleep(poll_interval)

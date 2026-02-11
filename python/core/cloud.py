"""Cloud client — device-code auth + project CRUD for AudioSync cloud.

Uses only stdlib (urllib) to avoid adding `requests` as a dependency.
All network calls raise descriptive exceptions on failure.
"""

from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Optional

import certifi

from PyQt6.QtCore import QSettings

from version import __version__

logger = logging.getLogger("audiosync.cloud")

# SSL context that works inside PyInstaller bundles (bundled CA certs).
_ssl_ctx = ssl.create_default_context(cafile=certifi.where())

API_BASE = "https://api.keyhan.info"
SETTINGS_ORG = "KeyhanStudio"
SETTINGS_APP = "AudioSyncPro"


class CloudError(Exception):
    """Raised when a cloud API call fails."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class CloudClient:
    """Client for the AudioSync cloud API.

    Handles device-code authentication and project CRUD.
    Token is persisted via QSettings.
    """

    def __init__(self, api_base: str = API_BASE) -> None:
        self._api_base = api_base.rstrip("/")
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

    # ----- Token management ---------------------------------------------------

    def set_token(self, token: str) -> None:
        """Store JWT token persistently."""
        self._settings.setValue("cloud/token", token)
        self._settings.sync()

    def get_token(self) -> Optional[str]:
        """Retrieve stored JWT token."""
        val = self._settings.value("cloud/token")
        return val if val else None

    def clear_token(self) -> None:
        """Remove stored token."""
        self._settings.remove("cloud/token")
        self._settings.sync()

    def is_authenticated(self) -> bool:
        """Check if we have a stored token."""
        return bool(self.get_token())

    # ----- User info ----------------------------------------------------------

    def get_user(self) -> dict:
        """Fetch current user info from the API.

        Returns dict with id, email, name, picture, role.
        Raises CloudError on failure (including 401).
        """
        return self._request("GET", "/auth/me")

    # ----- Device-code auth flow ----------------------------------------------

    def start_device_flow(self) -> dict:
        """Initiate device-code auth flow.

        Returns dict with:
            device_code, user_code, verification_uri, expires_in, interval
        """
        return self._request("POST", "/auth/device/code", body={
            "client_info": "AudioSync Pro Desktop",
        })

    def poll_device_token(
        self,
        device_code: str,
        interval: int = 5,
        timeout: int = 600,
    ) -> dict:
        """Poll for device token until authorized, expired, or timed out.

        Returns dict with token + user info on success.
        Raises CloudError on expiry or timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                result = self._request("POST", "/auth/device/token", body={
                    "device_code": device_code,
                })
                if result.get("success") and result.get("token"):
                    self.set_token(result["token"])
                    return result
                error = result.get("error", "")
                if error == "expired":
                    raise CloudError("Device code expired. Please try again.")
                if error == "authorization_pending":
                    time.sleep(interval)
                    continue
                # Unknown error
                raise CloudError(f"Unexpected response: {error}")
            except CloudError:
                raise
            except Exception as exc:
                logger.warning("Poll error: %s", exc)
                time.sleep(interval)

        raise CloudError("Authentication timed out. Please try again.")

    # ----- Project CRUD -------------------------------------------------------

    def list_projects(self) -> list[dict]:
        """List all cloud projects for the authenticated user."""
        result = self._request("GET", "/audiosync/projects")
        return result.get("projects", [])

    def save_project(
        self,
        name: str,
        data: dict,
        description: str = "",
        project_id: Optional[int] = None,
    ) -> dict:
        """Save (create or update) a project in the cloud.

        Returns the project info dict.
        """
        body = {"name": name, "description": description, "data": data}
        if project_id:
            result = self._request("PUT", f"/audiosync/projects/{project_id}", body=body)
        else:
            result = self._request("POST", "/audiosync/projects", body=body)
        return result.get("project", result)

    def load_project(self, project_id: int) -> dict:
        """Download a project from the cloud.

        Returns the full project dict including data.
        """
        result = self._request("GET", f"/audiosync/projects/{project_id}")
        return result.get("project", result)

    def delete_project(self, project_id: int) -> None:
        """Delete a project from the cloud."""
        self._request("DELETE", f"/audiosync/projects/{project_id}")

    def logout(self) -> None:
        """Sign out: clear the stored token."""
        self.clear_token()

    # ----- Internal HTTP -------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
    ) -> dict:
        """Make an authenticated HTTP request to the API.

        Returns parsed JSON dict. Raises CloudError on failure.
        """
        url = f"{self._api_base}{path}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"AudioSyncPro/{__version__}",
        }

        token = self.get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
                response_data = resp.read().decode("utf-8")
                if not response_data:
                    return {"success": True}
                return json.loads(response_data)
        except urllib.error.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            if exc.code == 401:
                raise CloudError("Authentication failed. Please sign in again.", 401)
            if exc.code == 403:
                error_msg = "Access denied"
                try:
                    error_data = json.loads(body_text)
                    error_msg = error_data.get("error", error_msg)
                except Exception:
                    pass
                raise CloudError(error_msg, 403)
            if exc.code == 404:
                raise CloudError("Resource not found.", 404)

            # Try to extract error message from response body
            try:
                error_data = json.loads(body_text)
                msg = error_data.get("error", f"HTTP {exc.code}")
            except Exception:
                msg = f"HTTP {exc.code}: {body_text[:200]}"

            raise CloudError(msg, exc.code)

        except urllib.error.URLError as exc:
            raise CloudError(f"Network error: {exc.reason}")
        except Exception as exc:
            raise CloudError(f"Request failed: {exc}")

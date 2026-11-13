"""API client for Bitaxe miner."""

import asyncio
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10


class BitaxeApiError(Exception):
    """Base exception for Bitaxe API errors."""


class BitaxeConnectionError(BitaxeApiError):
    """Exception for connection errors."""


class BitaxeTimeoutError(BitaxeConnectionError):
    """Exception for timeout errors."""


class BitaxeApiClient:
    """API client for Bitaxe miner."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self.host = host
        self.session = session
        self._base_url = f"http://{host}"

    async def _async_request(self, method: str, endpoint: str) -> tuple[int, str | None, str]:
        """Send a request and return the status, content type and body."""
        url = f"{self._base_url}{endpoint}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self.session.request(method, url, allow_redirects=False) as response:
                    text = await response.text(errors="replace")
                    return response.status, response.content_type, text
        except TimeoutError as err:
            _LOGGER.debug("Timeout on %s %s", method, url)
            raise BitaxeTimeoutError(f"Timeout connecting to {self.host}") from err
        except aiohttp.ClientError as err:
            _LOGGER.debug("Error on %s %s: %s", method, url, err)
            raise BitaxeConnectionError(f"Cannot connect to {self.host}: {err}") from err

    async def async_get_data(self, endpoint: str) -> dict[str, Any]:
        """Get a JSON object from the API."""
        status, content_type, text = await self._async_request("GET", endpoint)
        _LOGGER.debug("Response from %s (first 200 chars): %s", endpoint, text[:200])
        if status != 200:
            raise BitaxeApiError(f"HTTP {status} error from {endpoint}")
        return self._parse_object(endpoint, content_type, text)

    async def async_post(self, endpoint: str) -> None:
        """Send a command to the API."""
        status, _, _ = await self._async_request("POST", endpoint)
        if status >= 400:
            raise BitaxeApiError(f"HTTP {status} error from {endpoint}")

    @staticmethod
    def _parse_object(endpoint: str, content_type: str | None, text: str) -> dict[str, Any]:
        """Parse a response body that must contain a JSON object."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            _LOGGER.debug(
                "Invalid JSON from %s. Content-Type: %s, Response: %s",
                endpoint,
                content_type,
                text[:500],
            )
            raise BitaxeApiError(f"Invalid JSON response from {endpoint}: {err}") from err
        if not isinstance(data, dict):
            raise BitaxeApiError(
                f"Expected a JSON object from {endpoint}, got {type(data).__name__}"
            )
        return data

    async def async_pause_mining(self) -> None:
        """Pause mining."""
        await self.async_post("/api/system/pause")

    async def async_resume_mining(self) -> None:
        """Resume mining."""
        await self.async_post("/api/system/resume")

    async def async_shutdown(self) -> None:
        """Shut down the ASICs (NerdQAxe firmware)."""
        await self.async_post("/api/system/shutdown")

    async def async_restart(self) -> None:
        """Restart the device."""
        await self.async_post("/api/system/restart")

    async def async_get_dashboard(self) -> dict[str, Any] | None:
        """Get the NerdQAxe v2 dashboard, or None if the firmware lacks it.

        Raises BitaxeApiError for errors that may be temporary, so the caller
        only gives up on the dashboard when the firmware really lacks it.
        """
        endpoint = "/api/v2/dashboard"
        status, content_type, text = await self._async_request("GET", endpoint)
        # Unknown endpoints redirect to the captive portal or serve the web UI
        if (
            300 <= status < 400
            or status == 404
            or (status == 200 and content_type != "application/json")
        ):
            _LOGGER.debug("No v2 dashboard at %s (HTTP %s)", endpoint, status)
            return None
        if status != 200:
            raise BitaxeApiError(f"HTTP {status} error from {endpoint}")
        return self._parse_object(endpoint, content_type, text)

    async def async_get_system_info(self) -> dict[str, Any]:
        """Get system information, which includes all mining data on AxeOS."""
        return await self.async_get_data("/api/system/info")

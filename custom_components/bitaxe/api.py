"""API client for Bitaxe miner."""
import asyncio
import json
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


class BitaxeApiError(Exception):
    """Base exception for Bitaxe API errors."""


class BitaxeConnectionError(BitaxeApiError):
    """Exception for connection errors."""


class BitaxeTimeoutError(BitaxeApiError):
    """Exception for timeout errors."""


class BitaxeApiClient:
    """API client for Bitaxe miner."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self.host = host
        self.session = session
        self._base_url = f"http://{host}"

    async def async_get_data(self, endpoint: str) -> dict:
        """Get data from the API."""
        url = f"{self._base_url}{endpoint}"
        try:
            async with asyncio.timeout(10):
                async with self.session.get(url, allow_redirects=False) as response:
                    response.raise_for_status()

                    # Get response text first for debugging
                    text = await response.text()

                    # Log first 200 chars for debugging
                    _LOGGER.debug("Response from %s (first 200 chars): %s", url, text[:200])

                    # Try to parse as JSON
                    try:
                        data = json.loads(text)
                        if not isinstance(data, dict):
                            raise ValueError(f"Expected dict, got {type(data)}")
                        return data
                    except json.JSONDecodeError as err:
                        _LOGGER.error(
                            "Invalid JSON from %s. Content-Type: %s, Response: %s",
                            url,
                            response.content_type,
                            text[:500]
                        )
                        raise BitaxeApiError(f"Invalid JSON response from {url}: {err}") from err

        except TimeoutError as err:
            _LOGGER.error("Timeout fetching data from %s after 10 seconds", url)
            raise BitaxeTimeoutError(f"Timeout connecting to {self.host}") from err
        except aiohttp.ClientConnectionError as err:
            _LOGGER.error("Connection error to %s: %s", url, err)
            raise BitaxeConnectionError(f"Cannot connect to {self.host}: {err}") from err
        except aiohttp.ClientResponseError as err:
            _LOGGER.error("HTTP %s error from %s: %s", err.status, url, err)
            raise BitaxeApiError(f"HTTP {err.status} error from {url}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP client error from %s: %s", url, err)
            raise BitaxeConnectionError(f"HTTP error connecting to {self.host}: {err}") from err

    async def async_post(self, endpoint: str) -> None:
        """Send a command to the API."""
        url = f"{self._base_url}{endpoint}"
        try:
            async with asyncio.timeout(10):
                async with self.session.post(url, allow_redirects=False) as response:
                    response.raise_for_status()
        except TimeoutError as err:
            _LOGGER.error("Timeout posting to %s after 10 seconds", url)
            raise BitaxeTimeoutError(f"Timeout connecting to {self.host}") from err
        except aiohttp.ClientConnectionError as err:
            _LOGGER.error("Connection error to %s: %s", url, err)
            raise BitaxeConnectionError(f"Cannot connect to {self.host}: {err}") from err
        except aiohttp.ClientResponseError as err:
            _LOGGER.error("HTTP %s error from %s: %s", err.status, url, err)
            raise BitaxeApiError(f"HTTP {err.status} error from {url}") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP client error from %s: %s", url, err)
            raise BitaxeConnectionError(f"HTTP error connecting to {self.host}: {err}") from err

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

    async def async_get_dashboard(self) -> dict | None:
        """Get the NerdQAxe v2 dashboard, or None if the firmware lacks it."""
        url = f"{self._base_url}/api/v2/dashboard"
        try:
            async with asyncio.timeout(10):
                async with self.session.get(url, allow_redirects=False) as response:
                    # Unknown endpoints redirect to the captive portal
                    if response.status != 200 or response.content_type != "application/json":
                        _LOGGER.debug("No v2 dashboard at %s (HTTP %s)", url, response.status)
                        return None
                    data = await response.json()
        except TimeoutError as err:
            raise BitaxeTimeoutError(f"Timeout connecting to {self.host}") from err
        except (aiohttp.ClientError, ValueError) as err:
            raise BitaxeConnectionError(f"Error fetching {url}: {err}") from err
        return data if isinstance(data, dict) else None

    async def async_get_system_info(self) -> dict:
        """Get system information - used for validation during setup."""
        return await self.async_get_data("/api/system/info")

    async def async_get_status(self) -> dict:
        """Get mining status - AxeOS returns all data from /api/system/info."""
        return await self.async_get_data("/api/system/info")

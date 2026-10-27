"""DataUpdateCoordinator for Bitaxe."""
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BitaxeApiClient, BitaxeApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BitaxeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Bitaxe data."""

    def __init__(self, hass: HomeAssistant, client: BitaxeApiClient) -> None:
        """Initialize."""
        self.client = client
        # Whether the firmware has the v2 dashboard with per-chip hash rates,
        # None until probed
        self._dashboard_supported: bool | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            data = await self.client.async_get_status()
        except BitaxeApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # Only the NerdQAxe firmware fork reports a deviceModel; it exposes
        # per-chip hash rates through the v2 dashboard only
        if "deviceModel" in data and self._dashboard_supported is not False:
            try:
                dashboard = await self.client.async_get_dashboard()
            except BitaxeApiError as err:
                _LOGGER.debug("Error fetching dashboard: %s", err)
            else:
                self._dashboard_supported = dashboard is not None
                if dashboard is not None:
                    data["chips"] = dashboard.get("performance", {}).get("chips", [])

        return data

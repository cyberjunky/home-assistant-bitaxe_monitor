"""DataUpdateCoordinator for Bitaxe."""
from datetime import timedelta
import logging

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
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            return await self.client.async_get_status()
        except BitaxeApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
